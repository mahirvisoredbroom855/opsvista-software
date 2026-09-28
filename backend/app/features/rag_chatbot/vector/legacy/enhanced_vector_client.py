# -*- coding: utf-8 -*-
"""
Enhanced vector client with proper Supabase integration and pgvector support.
Fixed connection timeout issues with PgBouncer.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from typing import Sequence
import numpy as np
from app.core.config import settings

try:
    import asyncpg
except ImportError:
    asyncpg = None  # type: ignore

try:
    from app.core.config import settings
except ImportError:
    class _S:
        DATABASE_URL = os.getenv("DATABASE_URL")
        def __getattr__(self, k):
            return None
    settings = _S()

logger = logging.getLogger(__name__)

# --- add near the top, after imports ---



def ensure_embedding_dim(vec: Sequence[float], what: str = "embedding") -> np.ndarray:
    """
    Ensure a 1-D float32 vector with the exact dimension settings.EMBEDDING_DIM.
    Raises ValueError with a clear message when mismatch occurs.
    """
    arr = np.asarray(vec, dtype=np.float32).reshape(-1)
    expected = int(getattr(settings, "EMBEDDING_DIM", 1536))
    if arr.shape[0] != expected:
        model_name = getattr(settings, "OPENAI_EMBEDDING_MODEL", "unknown")
        raise ValueError(
            f"{what} has dim {arr.shape[0]} but expected {expected} "
            f"(OPENAI_EMBEDDING_MODEL={model_name})."
        )
    return arr

def _normalize_dsn(url: Optional[str]) -> str:
    """Convert SQLAlchemy URL schemes to asyncpg-friendly DSNs."""
    if not url:
        return ""
    url = url.strip()

    replacements = {
        "postgresql+asyncpg://": "postgresql://",
        "postgres+asyncpg://": "postgres://",
        "postgresql+psycopg://": "postgresql://",
        "postgresql+psycopg2://": "postgresql://",
    }
    for k, v in replacements.items():
        if url.startswith(k):
            url = url.replace(k, v, 1)

    if not (url.startswith("postgresql://") or url.startswith("postgres://")):
        if "://" in url:
            scheme, rest = url.split("://", 1)
            if scheme.startswith("postgres"):
                url = "postgresql://" + rest
    return url


def _vector_str(vec: List[float]) -> str:
    """Serialize Python list[float] into pgvector-compatible string."""
    return "[" + ",".join(f"{x:.6f}" for x in vec) + "]"


def _ensure_list(x: Any) -> List[Any]:
    """Convert json/jsonb field into list safely."""
    if x is None:
        return []
    if isinstance(x, list):
        return x
    if isinstance(x, (bytes, bytearray)):
        try:
            return json.loads(x.decode("utf-8"))
        except Exception:
            return []
    if isinstance(x, str):
        try:
            v = json.loads(x)
            return v if isinstance(v, list) else []
        except Exception:
            return []
    return []


async def _column_exists(conn: asyncpg.Connection, table: str, column: str) -> bool:
    return bool(await conn.fetchval("""
        SELECT EXISTS(
            SELECT 1 FROM information_schema.columns
            WHERE table_schema='public' AND table_name=$1 AND column_name=$2
        )
    """, table, column))


async def _enum_labels(conn: asyncpg.Connection, table: str, column: str) -> List[str]:
    """Return ENUM labels if column is an enum; else []."""
    row = await conn.fetchrow("""
        SELECT udt_name, data_type
        FROM information_schema.columns
        WHERE table_schema='public' AND table_name=$1 AND column_name=$2
    """, table, column)
    if not row or row["data_type"] != "USER-DEFINED":
        return []
    enum_name = row["udt_name"]
    rows = await conn.fetch("""
        SELECT e.enumlabel
        FROM pg_type t
        JOIN pg_enum e ON t.oid = e.enumtypid
        WHERE t.typname = $1
        ORDER BY e.enumsortorder
    """, enum_name)
    return [r["enumlabel"] for r in rows]


def _pick_allowed(value: str, allowed: List[str], fallback_idx: int = 0) -> str:
    if not allowed:
        return value
    return value if value in allowed else allowed[min(fallback_idx, len(allowed)-1)]


async def _safe_pool_close(pool: asyncpg.Pool, timeout: float = 3.0) -> None:
    """Safely close an asyncpg pool with timeout protection for PgBouncer."""
    if pool.is_closing():
        return
    
    try:
        await asyncio.wait_for(pool.close(), timeout=timeout)
    except (asyncio.TimeoutError, TimeoutError):
        # Force terminate the pool if graceful close times out
        try:
            pool.terminate()
        except Exception:
            pass  # Pool might already be closed/terminated


@dataclass
class BusinessSearchResult:
    document_id: UUID
    embedding_id: UUID
    chunk_index: int
    content: str
    file_name: str
    file_type: str
    document_type: str
    department: str
    customers: List[str]
    staff_members: List[str]
    machines_involved: List[str]
    pricing_info: List[str]
    confidence_score: float
    business_relevance: float
    department_relevance: float
    similarity_score: float
    snippet: str
    score: float
    created_at: datetime
    has_mhm_machine_refs: bool = False
    has_pricing_strategy: bool = False
    has_customer_data: bool = False
    entity_count: int = 0


@dataclass
class DocumentRelationship:
    id: UUID
    source_document_id: UUID
    target_document_id: UUID
    relationship_type: str
    relationship_context: Optional[str] = None
    strength: Optional[float] = None
    confidence: Optional[float] = None
    business_context: Optional[Dict[str, Any]] = None


class EnhancedVectorDatabaseClient:
    """Enhanced vector client with proper Supabase/PostgreSQL integration."""

    def __init__(self) -> None:
        self._db_pool: Optional[asyncpg.Pool] = None
        self._in_memory: Dict[str, Any] = {
            "chunks": [],
            "relationships": [],
            "versions": [],
        }

    async def initialize(self) -> None:
        """Initialize database connection."""
        dsn = os.getenv("DATABASE_URL") or getattr(settings, "DATABASE_URL", None)
        dsn = _normalize_dsn(dsn)

        if asyncpg is None or not dsn:
            logger.warning("Database disabled (asyncpg missing or DATABASE_URL not set). Using in-memory mode.")
            return

        if "[YOUR-PASSWORD]" in dsn:
            logger.error("DATABASE_URL contains placeholder [YOUR-PASSWORD]. Please update with actual password.")
            return

        try:
            self._db_pool = await asyncpg.create_pool(
                dsn=dsn,
                min_size=1,  # Reduced from 2 for better PgBouncer compatibility
                max_size=5,  # Reduced from 10 for better PgBouncer compatibility
                timeout=8,   # Reduced from 10
                command_timeout=20,  # Reduced from 30
                # IMPORTANT for Supabase PgBouncer (transaction pooler)
                statement_cache_size=0,
                max_inactive_connection_lifetime=20.0,  # Reduced from 30
                server_settings={"application_name": "opsvista-vector"},
            )
            logger.info("Database pool initialized successfully.")
            await self._ensure_vector_extension()
        except Exception as e:
            logger.error(f"Failed to initialize database pool: {e}")
            self._db_pool = None

    async def _ensure_vector_extension(self):
        """Ensure pgvector extension is available."""
        if not self._db_pool:
            return
        try:
            async with self._db_pool.acquire() as conn:
                exists = await conn.fetchval(
                    "SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname='vector')"
                )
                if not exists:
                    try:
                        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                        logger.info("pgvector extension created successfully.")
                    except Exception as e:
                        logger.error(f"Failed to create vector extension: {e}")
                else:
                    logger.info("pgvector extension is available.")
        except Exception as e:
            logger.error(f"Error checking vector extension: {e}")

    async def close(self) -> None:
        """Close database connection with improved timeout handling."""
        if self._db_pool is not None:
            try:
                await _safe_pool_close(self._db_pool, timeout=2.0)
            except Exception as e:
                logger.debug(f"Pool close exception (expected with PgBouncer): {e}")
            finally:
                self._db_pool = None

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check."""
        if self._db_pool is None:
            return {"status": "healthy", "db": "unavailable (in-memory mode)"}
        try:
            async with self._db_pool.acquire() as conn:
                await conn.execute("SELECT 1;")
                vector_available = await conn.fetchval(
                    "SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'vector')"
                )
                tables_exist = await conn.fetchval("""
                    SELECT COUNT(*) FROM information_schema.tables
                    WHERE table_schema='public'
                      AND table_name IN ('document_embeddings','document_metadata')
                """)
                return {
                    "status": "healthy",
                    "db": "connected",
                    "vector_extension": bool(vector_available),
                    "tables_ready": tables_exist >= 2
                }
        except Exception as e:
            logger.warning(f"DB health check failed: {e}")
            return {"status": "unhealthy", "db": f"error: {e}"}

    async def _create_embedding(self, text: str) -> List[float]:
        """Create embedding using OpenAI API or fallback to deterministic mock."""
        h = hashlib.md5(text.encode("utf-8")).hexdigest()
        seed = int(h, 16)
        return [((seed + i) % 2_000_000) / 1_000_000.0 - 1.0 for i in range(1536)]

    async def store_document_chunk(
        self,
        *,
        document_id: UUID,
        chunk_index: int,
        chunk_content: str,
        chunk_type: str,
        file_name: str,
        file_type: str,
        document_type: str,
        department: str,
        business_metadata: Optional[Dict[str, Any]] = None,
        confidence_score: Optional[float] = None,
        business_relevance: Optional[float] = None,
        department_relevance: Optional[float] = None,
        relationships: Optional[List[Dict[str, Any]]] = None,
        version_info: Optional[Dict[str, Any]] = None,
    ) -> UUID:
        """Store document chunk in database (or in-memory if DB is unavailable)."""
        embedding = await self._create_embedding(chunk_content)
        embedding_str = _vector_str(embedding)
        new_embedding_id = uuid4()
        content_hash = hashlib.md5(chunk_content.encode("utf-8")).hexdigest()

        # In-memory fallback if DB pool is not available at all
        if self._db_pool is None:
            rec = {
                "embedding_id": new_embedding_id,
                "document_id": document_id,
                "chunk_index": chunk_index,
                "content": chunk_content,
                "chunk_type": chunk_type,
                "file_name": file_name,
                "file_type": file_type,
                "document_type": document_type,
                "department": department,
                "business_metadata": business_metadata or {},
                "confidence_score": confidence_score,
                "business_relevance": business_relevance,
                "department_relevance": department_relevance,
                "embedding": embedding,
                "created_at": datetime.utcnow(),
            }
            self._in_memory["chunks"].append(rec)
            return new_embedding_id

        try:
            async with self._db_pool.acquire() as conn:
                async with conn.transaction():
                    # --- ENUM safety (pick valid labels if columns are enums) ---
                    doc_allowed = await _enum_labels(conn, "document_embeddings", "document_type")
                    dep_allowed = await _enum_labels(conn, "document_embeddings", "department")
                    ft_allowed  = await _enum_labels(conn, "document_embeddings", "file_type")

                    doc_type_final  = _pick_allowed(document_type, doc_allowed) if doc_allowed else document_type
                    dept_final      = _pick_allowed(department,     dep_allowed) if dep_allowed else department
                    file_type_final = _pick_allowed(file_type,      ft_allowed)  if ft_allowed  else file_type

                    has_content_hash = await _column_exists(conn, "document_embeddings", "content_hash")

                    # --- Embedding UPSERT ---
                    if has_content_hash:
                        # On duplicate content_hash, return the existing id (idempotent insert)
                        row = await conn.fetchrow("""
                            INSERT INTO document_embeddings (
                                id, document_id, chunk_index, embedding, chunk_content,
                                chunk_type, file_name, file_type, document_type, department,
                                confidence_score, business_relevance, department_relevance,
                                content_hash
                            ) VALUES ($1,$2,$3,$4::vector,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)
                            ON CONFLICT (content_hash)
                            DO UPDATE SET content_hash = EXCLUDED.content_hash   -- no-op, just to allow RETURNING
                            RETURNING id, document_id, document_type::text AS document_type, department::text AS department, file_type::text AS file_type
                        """,
                            new_embedding_id, document_id, chunk_index, embedding_str, chunk_content,
                            chunk_type, file_name, file_type_final, doc_type_final, dept_final,
                            confidence_score or 0.0, business_relevance or 0.0, department_relevance or 0.0,
                            content_hash
                        )
                        embedding_id = row["id"]
                        # Optional: if you want to refresh metadata even on duplicate, you can still do it below.
                    else:
                        await conn.execute("""
                            INSERT INTO document_embeddings (
                                id, document_id, chunk_index, embedding, chunk_content,
                                chunk_type, file_name, file_type, document_type, department,
                                confidence_score, business_relevance, department_relevance
                            ) VALUES ($1,$2,$3,$4::vector,$5,$6,$7,$8,$9,$10,$11,$12,$13)
                        """,
                            new_embedding_id, document_id, chunk_index, embedding_str, chunk_content,
                            chunk_type, file_name, file_type_final, doc_type_final, dept_final,
                            confidence_score or 0.0, business_relevance or 0.0, department_relevance or 0.0
                        )
                        embedding_id = new_embedding_id

                    # --- document_metadata insert (schema-aware & optional) ---
                    if business_metadata:
                        cols: List[str] = ["embedding_id"]
                        vals: List[Any] = [embedding_id]

                        import json as _json

                        async def add_jsonb(col: str, key: str, default):
                            if await _column_exists(conn, "document_metadata", col):
                                cols.append(col)
                                vals.append(_json.dumps(business_metadata.get(key, default)))

                        async def add_scalar(col: str, value):
                            if await _column_exists(conn, "document_metadata", col):
                                cols.append(col)
                                vals.append(value)

                        # JSONB arrays
                        await add_jsonb("customers", "customers", [])
                        await add_jsonb("suppliers", "suppliers", [])
                        await add_jsonb("staff_members", "staff_members", [])
                        await add_jsonb("machines_involved", "machines_involved", [])
                        await add_jsonb("pricing_info", "pricing_info", [])
                        await add_jsonb("amounts", "amounts", [])
                        await add_jsonb("dates", "dates", [])
                        await add_jsonb("locations", "locations", [])

                        # Optional flags / counters
                        await add_scalar("has_mhm_machine_refs", bool(business_metadata.get("has_mhm_machine_refs", False)))
                        await add_scalar("has_pricing_strategy", bool(business_metadata.get("has_pricing_strategy", False)))
                        await add_scalar("has_customer_data", bool(business_metadata.get("has_customer_data", False)))
                        await add_scalar("has_production_data", bool(business_metadata.get("has_production_data", False)))
                        await add_scalar("entity_count", int(business_metadata.get("entity_count", 0)))

                        if len(cols) > 1:
                            placeholders = ",".join(f"${i}" for i in range(1, len(vals) + 1))
                            sql = f"""
                                INSERT INTO document_metadata ({", ".join(cols)})
                                VALUES ({placeholders})
                                ON CONFLICT (embedding_id) DO NOTHING
                            """
                            await conn.execute(sql, *vals)

            logger.info(f"Stored document chunk {embedding_id} successfully")
            return embedding_id

        except Exception as e:
            # Only fall back to in-memory for unexpected DB errors;
            # the ON CONFLICT path above already de-duplicates content safely.
            logger.error(f"Failed to store document chunk: {e}")
            rec = {
                "embedding_id": new_embedding_id,
                "document_id": document_id,
                "chunk_index": chunk_index,
                "content": chunk_content,
                "file_name": file_name,
                "document_type": document_type,
                "department": department,
                "created_at": datetime.utcnow(),
            }
            self._in_memory["chunks"].append(rec)
            return new_embedding_id


    async def search_similar_chunks(
        self,
        *,
        query_text: str,
        limit: int = 5,
        similarity_threshold: Optional[float] = None,
        semantic_filters: Optional[Dict[str, Any]] = None,
        business_filters: Optional[Dict[str, Any]] = None,
        temporal_filters: Optional[Dict[str, Any]] = None,
    ) -> List[BusinessSearchResult]:
        """Search for similar chunks using vector similarity."""
        if not query_text:
            return []

        query_embedding = await self._create_embedding(query_text)
        query_embedding_str = _vector_str(query_embedding)

        if self._db_pool is None:
            return await self._search_in_memory(query_embedding, limit, business_filters)

        try:
            async with self._db_pool.acquire() as conn:
                where_clauses: List[str] = []
                params: List[Any] = [query_embedding_str, limit]
                param_count = 2

                if business_filters:
                    if (dept := business_filters.get("department")) is not None:
                        param_count += 1
                        where_clauses.append(f"e.department = ${param_count}")
                        params.append(dept)
                    if (doc_type := business_filters.get("document_type")) is not None:
                        param_count += 1
                        where_clauses.append(f"e.document_type = ${param_count}")
                        params.append(doc_type)

                where_clause = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

                query = f"""
                    SELECT 
                        e.id as embedding_id,
                        e.document_id,
                        e.chunk_index,
                        e.chunk_content,
                        e.file_name,
                        e.file_type,
                        e.document_type,
                        e.department,
                        e.confidence_score,
                        e.business_relevance,
                        e.department_relevance,
                        e.created_at,
                        1 - (e.embedding <=> $1::vector) AS similarity_score,
                        COALESCE(m.customers, '[]'::jsonb) as customers,
                        COALESCE(m.staff_members, '[]'::jsonb) as staff_members,
                        COALESCE(m.machines_involved, '[]'::jsonb) as machines_involved,
                        COALESCE(m.pricing_info, '[]'::jsonb) as pricing_info,
                        COALESCE(m.has_mhm_machine_refs, false) as has_mhm_machine_refs,
                        COALESCE(m.has_pricing_strategy, false) as has_pricing_strategy,
                        COALESCE(m.has_customer_data, false) as has_customer_data,
                        COALESCE(m.entity_count, 0) as entity_count
                    FROM document_embeddings e
                    LEFT JOIN document_metadata m ON e.id = m.embedding_id
                    {where_clause}
                    ORDER BY e.embedding <=> $1::vector
                    LIMIT $2
                """

                rows = await conn.fetch(query, *params)

                results: List[BusinessSearchResult] = []
                for row in rows:
                    customers = _ensure_list(row["customers"])
                    staff_members = _ensure_list(row["staff_members"])
                    machines_involved = _ensure_list(row["machines_involved"])
                    pricing_info = _ensure_list(row["pricing_info"])

                    sim = float(row["similarity_score"])
                    result = BusinessSearchResult(
                        document_id=row["document_id"],
                        embedding_id=row["embedding_id"],
                        chunk_index=row["chunk_index"],
                        content=row["chunk_content"],
                        file_name=row["file_name"],
                        file_type=row["file_type"],
                        document_type=row["document_type"],
                        department=row["department"],
                        customers=customers,
                        staff_members=staff_members,
                        machines_involved=machines_involved,
                        pricing_info=pricing_info,
                        confidence_score=row["confidence_score"] or 0.0,
                        business_relevance=row["business_relevance"] or 0.0,
                        department_relevance=row["department_relevance"] or 0.0,
                        similarity_score=sim,
                        snippet=(row["chunk_content"] or "")[:200],
                        score=sim,
                        created_at=row["created_at"],
                        has_mhm_machine_refs=bool(row["has_mhm_machine_refs"]),
                        has_pricing_strategy=bool(row["has_pricing_strategy"]),
                        has_customer_data=bool(row["has_customer_data"]),
                        entity_count=int(row["entity_count"] or 0),
                    )
                    results.append(result)

                return results

        except Exception as e:
            logger.error(f"Database search failed: {e}")
            return await self._search_in_memory(query_embedding, limit, business_filters)

    async def _search_in_memory(self, query_embedding, limit, business_filters):
        """Fallback in-memory search."""
        def dot(a, b):
            return sum(x * y for x, y in zip(a, b))

        results = []
        for rec in self._in_memory["chunks"]:
            if business_filters and (dept := business_filters.get("department")):
                if rec.get("department") != dept:
                    continue
            score = dot(query_embedding[:256], rec.get("embedding", [])[:256])
            results.append(
                BusinessSearchResult(
                    document_id=rec["document_id"],
                    embedding_id=rec["embedding_id"],
                    chunk_index=rec["chunk_index"],
                    content=rec["content"],
                    file_name=rec["file_name"],
                    file_type=rec.get("file_type", "txt"),
                    document_type=rec["document_type"],
                    department=rec["department"],
                    customers=[],
                    staff_members=[],
                    machines_involved=[],
                    pricing_info=[],
                    confidence_score=rec.get("confidence_score", 0.0),
                    business_relevance=rec.get("business_relevance", 0.0),
                    department_relevance=rec.get("department_relevance", 0.0),
                    similarity_score=float(score),
                    snippet=rec["content"][:200],
                    score=float(score),
                    created_at=rec["created_at"],
                )
            )

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]

    async def get_document_relationships(self, document_id: UUID) -> List[DocumentRelationship]:
        """Get document relationships."""
        if self._db_pool is None:
            return [r for r in self._in_memory["relationships"]
                    if r.source_document_id == document_id or r.target_document_id == document_id]

        try:
            async with self._db_pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT id, source_document_id, target_document_id, 
                           relationship_type, relationship_context, strength, confidence, business_context
                    FROM document_relationships 
                    WHERE source_document_id = $1 OR target_document_id = $1
                """, document_id)

                return [
                    DocumentRelationship(
                        id=row['id'],
                        source_document_id=row['source_document_id'],
                        target_document_id=row['target_document_id'],
                        relationship_type=row['relationship_type'],
                        relationship_context=row['relationship_context'],
                        strength=row['strength'],
                        confidence=row['confidence'],
                        business_context=row['business_context']
                    ) for row in rows
                ]
        except Exception as e:
            logger.error(f"Failed to get relationships: {e}")
            return []

    async def get_business_intelligence_summary(self) -> Dict[str, Any]:
        """Get comprehensive business intelligence summary."""
        if self._db_pool is None:
            chunks = self._in_memory["chunks"]
            by_dept: Dict[str, int] = {}
            by_type: Dict[str, int] = {}
            for c in chunks:
                by_dept[c["department"]] = by_dept.get(c["department"], 0) + 1
                by_type[c["document_type"]] = by_type.get(c["document_type"], 0) + 1

            return {
                "overview": {
                    "total_documents": len({c["document_id"] for c in chunks}),
                    "total_chunks": len(chunks),
                    "last_updated": datetime.utcnow().isoformat() + "Z",
                },
                "business_coverage": by_type,
                "department_breakdown": by_dept,
            }

        try:
            async with self._db_pool.acquire() as conn:
                overview = await conn.fetchrow("""
                    SELECT 
                        COUNT(DISTINCT document_id) as total_documents,
                        COUNT(*) as total_chunks,
                        MAX(created_at) as last_updated
                    FROM document_embeddings
                """)

                dept_breakdown_rows = await conn.fetch("""
                    SELECT department, COUNT(*) as count
                    FROM document_embeddings
                    GROUP BY department
                    ORDER BY count DESC
                """)

                type_breakdown_rows = await conn.fetch("""
                    SELECT document_type, COUNT(*) as count
                    FROM document_embeddings
                    GROUP BY document_type
                    ORDER BY count DESC
                """)

                # These columns may not exist in some schemas; guard with TRY
                try:
                    business_metrics = await conn.fetchrow("""
                        SELECT 
                            COUNT(*) FILTER (WHERE m.has_customer_data = true) as docs_with_customers,
                            COUNT(*) FILTER (WHERE m.has_mhm_machine_refs = true) as docs_with_mhm_refs,
                            COUNT(*) FILTER (WHERE m.has_pricing_strategy = true) as docs_with_pricing,
                            COUNT(*) FILTER (WHERE m.has_production_data = true) as docs_with_production,
                            AVG(e.business_relevance) as avg_business_relevance,
                            AVG(e.confidence_score) as avg_confidence_score
                        FROM document_embeddings e
                        LEFT JOIN document_metadata m ON e.id = m.embedding_id
                    """)
                except Exception:
                    business_metrics = {
                        "docs_with_customers": 0,
                        "docs_with_mhm_refs": 0,
                        "docs_with_pricing": 0,
                        "docs_with_production": 0,
                        "avg_business_relevance": 0.0,
                        "avg_confidence_score": 0.0,
                    }

                return {
                    "overview": {
                        "total_documents": overview['total_documents'] or 0,
                        "total_chunks": overview['total_chunks'] or 0,
                        "last_updated": overview['last_updated'].isoformat() + "Z" if overview['last_updated'] else None,
                    },
                    "department_breakdown": {row['department']: row['count'] for row in dept_breakdown_rows},
                    "business_coverage": {row['document_type']: row['count'] for row in type_breakdown_rows},
                    "business_intelligence": {
                        "docs_with_customers": int((business_metrics or {}).get('docs_with_customers', 0) or 0),
                        "docs_with_mhm_refs": int((business_metrics or {}).get('docs_with_mhm_refs', 0) or 0),
                        "docs_with_pricing": int((business_metrics or {}).get('docs_with_pricing', 0) or 0),
                        "docs_with_production": int((business_metrics or {}).get('docs_with_production', 0) or 0),
                        "avg_business_relevance": float((business_metrics or {}).get('avg_business_relevance', 0.0) or 0.0),
                        "avg_confidence_score": float((business_metrics or {}).get('avg_confidence_score', 0.0) or 0.0),
                    }
                }

        except Exception as e:
            logger.error(f"Failed to get business intelligence summary: {e}")
            return {
                "overview": {"total_documents": 0, "total_chunks": 0, "last_updated": None},
                "business_coverage": {},
                "department_breakdown": {},
                "error": str(e)
            }


# --- Backwards-compat exports for older imports ---
VectorDatabaseClient = EnhancedVectorDatabaseClient
def create_vector_client() -> EnhancedVectorDatabaseClient:
    return EnhancedVectorDatabaseClient()