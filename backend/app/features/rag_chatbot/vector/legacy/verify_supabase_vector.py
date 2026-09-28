# backend/app/features/rag_chatbot/vector/verify_supabase_vector.py
from __future__ import annotations

from dotenv import load_dotenv
load_dotenv("../.env")   # <- note the parent path since you run from backend/

import os, uuid, traceback, asyncpg, asyncio
from typing import List, Tuple, Optional

async def _enum_labels(conn: asyncpg.Connection, table: str, column: str) -> List[str]:
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

import os
import sys
import asyncio
import textwrap
import uuid
from dataclasses import dataclass
from typing import List, Tuple

try:
    import asyncpg
except Exception as e:
    print("❌ asyncpg not installed. Run: pip install asyncpg")
    raise

# Load .env if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# Import your vector client from this package
from .enhanced_vector_client import EnhancedVectorDatabaseClient

# ----------------------------
# Config toggles
# ----------------------------
CLEANUP_AFTER = True   # set False if you want to inspect rows in Supabase after the run
EMBED_DIM = 1536       # must match your model & table definition


@dataclass
class Step:
    name: str
    ok: bool
    detail: str = ""


def _mask_dsn(dsn: str) -> str:
    try:
        import urllib.parse as up
        p = up.urlparse(dsn)
        netloc = p.netloc
        if "@" in netloc:
            userinfo, host = netloc.split("@", 1)
            if ":" in userinfo:
                user, _pw = userinfo.split(":", 1)
            else:
                user = userinfo
            netloc = f"{user}:***@{host}"
        return p._replace(netloc=netloc).geturl()
    except Exception:
        return dsn


async def ensure_schema(conn: asyncpg.Connection) -> None:
    """Ensure pgvector + the tables your EnhancedVectorDatabaseClient expects."""
    ddl = f"""
    create extension if not exists vector;

    create table if not exists document_embeddings (
      id uuid primary key,
      document_id uuid not null,
      chunk_index int not null,
      embedding vector({EMBED_DIM}) not null,
      chunk_content text not null,
      chunk_type text,
      file_name text,
      file_type text,
      document_type text,
      department text,
      confidence_score double precision default 0,
      business_relevance double precision default 0,
      department_relevance double precision default 0,
      created_at timestamptz default now()
    );

    create table if not exists document_metadata (
      embedding_id uuid primary key references document_embeddings(id) on delete cascade,
      customers jsonb default '[]',
      suppliers jsonb default '[]',
      staff_members jsonb default '[]',
      machines_involved jsonb default '[]',
      pricing_info jsonb default '[]',
      amounts jsonb default '[]',
      dates jsonb default '[]',
      locations jsonb default '[]',
      has_mhm_machine_refs boolean default false,
      has_pricing_strategy boolean default false,
      has_customer_data boolean default false,
      has_production_data boolean default false,
      entity_count int default 0
    );

    create table if not exists document_relationships (
      id uuid primary key default gen_random_uuid(),
      source_document_id uuid not null,
      target_document_id uuid not null,
      relationship_type text not null,
      relationship_context text,
      strength double precision,
      confidence double precision,
      business_context jsonb
    );

    create index if not exists idx_doc_embed_embedding
      on document_embeddings using ivfflat (embedding vector_l2_ops) with (lists = 100);
    """
    await conn.execute(ddl)


def make_fake_embedding(seed_text: str, dim: int = EMBED_DIM) -> List[float]:
    # Same idea as your client: deterministic mock embedding for tests
    import hashlib
    h = hashlib.md5(seed_text.encode("utf-8")).hexdigest()
    seed = int(h, 16)
    return [((seed + i) % 2_000_000) / 1_000_000.0 - 1.0 for i in range(dim)]


async def safe_connection_close(conn: asyncpg.Connection, timeout: float = 2.0) -> None:
    """Safely close an asyncpg connection with timeout protection."""
    if conn.is_closed():
        return
    
    try:
        await asyncio.wait_for(conn.close(), timeout=timeout)
    except (asyncio.TimeoutError, TimeoutError):
        # Force terminate the connection if graceful close times out
        try:
            conn.terminate()
        except Exception:
            pass  # Connection might already be closed/terminated


async def direct_insert_and_query(conn: asyncpg.Connection, doc_label: str):
    """Proof that pgvector I/O works, adapted to schemas with NOT NULL content_hash."""
    import hashlib, uuid as _uuid
    document_id = _uuid.uuid4()
    embedding_id = _uuid.uuid4()
    chunk_index = 0
    content = f"This is a {doc_label} test chunk about MHM machines, pricing and RB Knit."

    # vector as string for pgvector
    embedding = make_fake_embedding(content)
    embedding_str = "[" + ",".join(f"{x:.6f}" for x in embedding) + "]"

    # generate a stable content hash (md5 of content)
    content_hash = hashlib.md5(content.encode("utf-8")).hexdigest()

    # (If your schema uses enums for these, adapt as needed)
    document_type = 'note'
    department = 'commercial'

    # Try to detect if content_hash column exists (works whether it exists or not)
    has_content_hash = await conn.fetchval("""
        SELECT EXISTS(
            SELECT 1 FROM information_schema.columns
            WHERE table_schema='public' AND table_name='document_embeddings'
              AND column_name='content_hash'
        )
    """)

    if has_content_hash:
        sql = """
        INSERT INTO document_embeddings (
            id, document_id, chunk_index, embedding, chunk_content,
            chunk_type, file_name, file_type, document_type, department,
            confidence_score, business_relevance, department_relevance,
            content_hash
        ) VALUES (
            $1, $2, $3, $4::vector, $5,
            'body', 'test_document.txt', 'txt', $6, $7,
            0.5, 0.6, 0.4, $8
        )
        """
        params = (embedding_id, document_id, chunk_index, embedding_str, content,
                  document_type, department, content_hash)
    else:
        sql = """
        INSERT INTO document_embeddings (
            id, document_id, chunk_index, embedding, chunk_content,
            chunk_type, file_name, file_type, document_type, department,
            confidence_score, business_relevance, department_relevance
        ) VALUES (
            $1, $2, $3, $4::vector, $5,
            'body', 'test_document.txt', 'txt', $6, $7,
            0.5, 0.6, 0.4
        )
        """
        params = (embedding_id, document_id, chunk_index, embedding_str, content,
                  document_type, department)

    await conn.execute(sql, *params)

    rows = await conn.fetch(
        """
        SELECT id, document_id, 1 - (embedding <=> $1::vector) AS sim
        FROM document_embeddings
        WHERE document_id = $2
        ORDER BY embedding <=> $1::vector
        LIMIT 1
        """,
        embedding_str, document_id
    )
    assert rows, "No rows found after insert"
    return document_id, rows[0]["id"]


async def test_vector_client_roundtrip() -> Tuple[uuid.UUID, uuid.UUID, str]:
    """
    Store a chunk with EnhancedVectorDatabaseClient and query it back.
    Uses enum labels from DB (no hardcoding).
    Fixed to properly handle connection cleanup.
    """
    from app.features.rag_chatbot.vector.enhanced_vector_client import EnhancedVectorDatabaseClient

    client = EnhancedVectorDatabaseClient()
    await client.initialize()
    hc = await client.health_check()
    if not (hc.get("db") == "connected" and hc.get("status") == "healthy"):
        raise RuntimeError(f"Vector client health check failed: {hc}")

    # Create a separate connection for enum discovery
    dsn = os.environ["DATABASE_URL"]
    conn2: Optional[asyncpg.Connection] = None
    
    try:
        # Use shorter timeouts and PgBouncer-friendly settings
        conn2 = await asyncpg.connect(
            dsn, 
            statement_cache_size=0, 
            command_timeout=10,  # Reduced from 15
            timeout=5  # Reduced connection timeout
        )
        
        dept_labels  = await _enum_labels(conn2, "document_embeddings", "department")
        dtype_labels = await _enum_labels(conn2, "document_embeddings", "document_type")
        ftype_labels = await _enum_labels(conn2, "document_embeddings", "file_type")
        
    except Exception as e:
        # If enum discovery fails, use fallback values
        print(f"Warning: Failed to discover enum labels: {e}")
        dept_labels = ["commercial", "production", "finance", "hr"]
        dtype_labels = ["note", "report", "invoice", "lc"]
        ftype_labels = ["txt", "pdf", "excel", "csv"]
    
    finally:
        # Safe connection cleanup
        if conn2:
            await safe_connection_close(conn2)

    dept  = _pick_allowed("commercial", dept_labels)
    dtype = _pick_allowed("note", dtype_labels)
    ftype = _pick_allowed("txt", ftype_labels)

    doc_id = uuid.uuid4()
    
    try:
        emb_id = await client.store_document_chunk(
            document_id=doc_id,
            chunk_index=0,
            chunk_content="Customer RB Knit placed a large order for MHM machine parts; pricing strategy discussed.",
            chunk_type="body",
            file_name="rb_knit_note.txt",
            file_type=ftype,
            document_type=dtype,
            department=dept,
            business_metadata={
                "customers": ["RB Knit"],
                "staff_members": ["Mizan"],
                "machines_involved": ["MHM"],
                "pricing_info": ["$5000+"],
                "has_mhm_machine_refs": True,
                "has_pricing_strategy": True,
                "has_customer_data": True,
                "entity_count": 3
            },
            confidence_score=0.7,
            business_relevance=0.8,
            department_relevance=0.9,
        )

        # Use the SAME labels for filters so we actually match what we inserted
        results = await client.search_similar_chunks(
            query_text="Find RB Knit orders above $5000 involving MHM",
            limit=3,
            business_filters={"department": dept, "document_type": dtype},
        )

        if not results:
            raise AssertionError("Roundtrip search returned 0 results (filter labels may not match).")
        
        return doc_id, emb_id, f"Found {len(results)} results; top.score={results[0].score:.3f}"
    
    finally:
        # Ensure client is properly closed
        await client.close()


async def main() -> int:
    import os, traceback, asyncpg
    steps: List[Step] = []

    dsn = os.getenv("DATABASE_URL", "")
    if not dsn:
        print("❌ DATABASE_URL not set. Put it in .env (quoted) or export it in your shell.")
        return 1
    print(f"🔗 Using DATABASE_URL: { _mask_dsn(dsn) }")

    conn: Optional[asyncpg.Connection] = None
    doc_id_a = emb_id_a = None  # direct insert
    doc_id_b = emb_id_b = None  # client roundtrip

    # 1) connect
    try:
        print("⏳ [1/5] Connecting to Supabase…")
        conn = await asyncpg.connect(
            dsn,
            timeout=10,              # connect timeout
            statement_cache_size=0,  # PgBouncer (transaction pooler) friendly
            command_timeout=15,      # per-statement timeout
        )
        print("✅ Connected")
        ver = await conn.fetchval("select version()")
        steps.append(Step("Connect to Supabase", True, ver.split()[0]))
    except Exception as e:
        steps.append(Step("Connect to Supabase", False, str(e)))
        return _report(steps)

    # 2) ensure pgvector + schema
    try:
        await ensure_schema(conn)
        pgv = await conn.fetchval(
            "select exists (select 1 from pg_extension where extname='vector')"
        )
        steps.append(Step("pgvector extension", bool(pgv), "installed" if pgv else "missing"))
        steps.append(Step("Schema", True, "document_embeddings / document_metadata / document_relationships ready"))
    except Exception as e:
        steps.append(Step("Schema", False, str(e)))
        await safe_connection_close(conn)
        return _report(steps)

    # 3) direct insert & query (DB-only proof)
    try:
        doc_id_a, emb_id_a = await direct_insert_and_query(conn, "direct")
        steps.append(Step("Direct vector insert+query", True, f"doc={doc_id_a}, emb={emb_id_a}"))
    except Exception as e:
        steps.append(Step("Direct vector insert+query", False, str(e)))
        await safe_connection_close(conn)
        return _report(steps)

    # 4) client roundtrip (app integration proof)
    try:
        print("⏳ [4/5] Client roundtrip (store + search + BI)…")
        doc_id_b, emb_id_b, detail = await test_vector_client_roundtrip()
        print("✅ Vector client roundtrip:", detail)
        steps.append(Step("Vector client roundtrip", True, detail))
    except Exception as e:
        print("❌ Vector client roundtrip:", repr(e))
        traceback.print_exc()  # show the exact failing line/SQL
        steps.append(Step("Vector client roundtrip", False, str(e)))
        # do NOT return yet; proceed to cleanup so the test rows from step 3 are removed

    # 5) cleanup (remove whatever we created)
    try:
        if CLEANUP_AFTER:
            if emb_id_a:
                await conn.execute("delete from document_metadata where embedding_id = $1", emb_id_a)
                await conn.execute("delete from document_embeddings where id = $1", emb_id_a)
            if emb_id_b:
                await conn.execute("delete from document_metadata where embedding_id = $1", emb_id_b)
                await conn.execute("delete from document_embeddings where id = $1", emb_id_b)
            steps.append(Step("Cleanup", True, "test rows removed"))
        else:
            steps.append(Step("Cleanup", True, "kept for inspection"))
    except Exception as e:
        steps.append(Step("Cleanup", False, str(e)))

    # safe close
    await safe_connection_close(conn)

    return _report(steps)


def _report(steps: List[Step]) -> int:
    print("\n==================================================")
    print(" Supabase + pgvector Integration Verification")
    print("==================================================")
    ok_all = True
    for s in steps:
        mark = "✅" if s.ok else "❌"
        print(f"{mark} {s.name}: {s.detail}")
        ok_all = ok_all and s.ok

    print("--------------------------------------------------")
    if ok_all:
        print("🎉 SUCCESS: Vector storage is integrated with Supabase pgvector and working end-to-end.")
        return 0
    else:
        print("⚠️  FAILED: See steps above. The most common issues are:")
        print(textwrap.dedent("""
            - Wrong DATABASE_URL (quote it in .env if it contains '&')
            - pgvector not installed (run: CREATE EXTENSION IF NOT EXISTS vector;)
            - Table schema mismatch (ensure document_embeddings has vector(1536))
            - Your client insert may need explicit '::vector' cast in SQL
            - Connection timeout issues with PgBouncer (use shorter timeouts)
        """).strip())
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))