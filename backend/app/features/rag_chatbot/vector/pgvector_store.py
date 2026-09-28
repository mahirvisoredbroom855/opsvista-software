"""
This file is OpsVista's second, backup place to search for an answer —
a copy of the same document data, but stored in the Supabase database
instead of a local file. It only gets used when the fast local search
isn't confident enough. This file also writes the permanent record of
every question ever asked (for the dashboard), and stores thumbs
up/down feedback.

backend/app/features/rag_chatbot/vector/pgvector_store.py

# ═══════════════════════════════════════════════════════════════════════
# MODULE: [OPS:PVEC] — the pgvector fallback + audit-trail layer
#
# Every function here is independently tagged (OPS:PVEC-001..009) below. The
# short version of what this module is for: a second retrieval path
# (pgvector_search) that only fires when the primary in-memory index
# [OPS:IDX] comes up empty or low-confidence, plus the audit-trail writes
# (log_query, upsert_query_embedding, set_feedback) that make the
# similar-questions feature and the /feedback endpoint real, not stubs.
# ═══════════════════════════════════════════════════════════════════════

The real pgvector-backed fallback path described in the RAG documentation's
dual-path retrieval design (enhanced_index.json = primary, pgvector =
fallback) and the Development Specification's Supabase schema
(dim_document/fact_chunk/fact_embedding/fact_query/bridge_query_citation).

This replaces the previously-dormant integrated_search_system.py /
search_integration.py scaffolding, which never actually implemented a vector
backend (see backend/sql/schema.sql for the table/RPC definitions this
module talks to).

Two responsibilities:
  1. upsert_documents(documents) — dual-write: called right after the JSON
     index is (re)built, so pgvector always has the same corpus as
     enhanced_index.json, not a stale or empty copy.
  2. pgvector_search(query, top_k) — the actual fallback query, used by
     chat.py when the primary (JSON) index returns nothing or low-confidence
     results.

Everything here is best-effort: if Supabase isn't configured yet (no
SUPABASE_URL/SERVICE_ROLE_KEY) or the schema hasn't been applied, functions
degrade to returning empty/zero rather than raising, so the primary path
keeps working regardless.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

from .persisted_inmemory_search import embed_texts

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────
# [OPS:PVEC-001] _get_service_client() / is_configured() / get_service_client()
#
# WHAT: constructs a service-role Supabase client (bypasses Row Level
#       Security — contrast with the anon-key client in auth_deps.py
#       [OPS:AUTH-002], which enforces RLS for user-facing reads). Every
#       other function in this module calls _get_service_client() itself
#       rather than taking a client parameter, so is_configured() can be
#       called cheaply and independently anywhere in the request path.
# BREAKS IF: SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY missing/placeholder
#       — returns None rather than raising, which is what makes every
#       pgvector function in this file degrade gracefully instead of
#       500ing when Supabase isn't configured yet.
# CALLED BY: every other function in this file; is_configured() also used
#       directly by [OPS:CHAT-022] GET /status.
# ─────────────────────────────────────────────────────────────────────────
def _get_service_client():
    """Lazy import + construct so this module never fails to import even
    without Supabase configured, and always reads current env (not whatever
    was cached at process start)."""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY")
    if not url or not key or "placeholder" in url:
        return None
    try:
        from supabase import create_client
        return create_client(url, key)
    except Exception as e:
        logger.warning(f"Could not create Supabase client: {e}")
        return None


def is_configured() -> bool:
    return _get_service_client() is not None


def get_service_client():
    """Public accessor for other modules (e.g. admin_metrics.py) that need
    the raw Supabase client for queries beyond what this module exposes."""
    return _get_service_client()


# ─────────────────────────────────────────────────────────────────────────
# [OPS:PVEC-002] _document_source_path() — the stable identity key used to
#                 tie a document to the same dim_document row every time
#
# WHAT: Drive files use their immutable drive_file_id; local seed_docs
#       files use "owner_folder/file_name" instead since they have no
#       Drive ID. This exact key is what [OPS:PVEC-003] upsert_documents()
#       upserts on and what [OPS:PVEC-005] log_query() re-derives to link
#       citations back to the right document — the two must always agree.
# ─────────────────────────────────────────────────────────────────────────
def _document_source_path(metadata: Dict[str, Any]) -> str:
    """Stable unique key for a document, independent of source (Drive vs local)."""
    if metadata.get("drive_file_id"):
        return str(metadata["drive_file_id"])
    return f"{metadata.get('owner_folder', '')}/{metadata.get('file_name', 'unknown')}"


# ─────────────────────────────────────────────────────────────────────────
# [OPS:PVEC-003] upsert_documents() — the dual-write path
#
# API/CALL: Supabase REST writes to dim_document / fact_chunk /
#       fact_embedding (three tables per chunk); Gemini embed_content via
#       [OPS:IDX-002] embed_texts() — only when a chunk doesn't already
#       carry a precomputed vector.
# WHY REUSE PRECOMPUTED VECTORS: this is called right after
#       [OPS:IDX-004] PersistedInMemorySearch.ingest_documents() has
#       already embedded the same chunks for the JSON index — re-embedding
#       here would double the Gemini API cost/latency of every ingestion
#       run for no benefit, since both paths need the identical vector.
# CALLED BY: build_local_index.py [OPS:ING-002], build_drive_index.py
#       [OPS:DRIVE-003] — right after the JSON index is (re)built, so
#       pgvector's corpus never drifts out of sync with enhanced_index.json.
# BREAKS IF: called with chunks whose IDs/order don't match what was just
#       written to enhanced_index.json — the two stores would silently
#       diverge until the next full rebuild.
# ─────────────────────────────────────────────────────────────────────────
def upsert_documents(documents: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Dual-write path: takes chunk dicts shaped like PersistedInMemorySearch's
    `items` — [{id, text, metadata, vector?}] — and upserts dim_document /
    fact_chunk / fact_embedding rows in Supabase. If a chunk already carries
    a precomputed "vector" (e.g. passed straight from index.items after
    PersistedInMemorySearch.ingest_documents() already embedded it), that
    vector is reused instead of re-embedding — otherwise every dual-write
    would silently double the embedding API calls/cost of every index build.

    Returns a small stats dict; never raises (logs and returns partial
    results on failure) so a Supabase outage never blocks the primary
    JSON-index build.
    """
    client = _get_service_client()
    if client is None:
        logger.info("[pgvector] Supabase not configured — skipping dual-write.")
        return {"skipped": True, "documents": 0, "chunks": 0, "embeddings": 0}

    # Group chunks by their parent document so we upsert each document once.
    by_doc: Dict[str, List[Dict[str, Any]]] = {}
    for doc in documents:
        meta = doc.get("metadata", {})
        key = _document_source_path(meta)
        by_doc.setdefault(key, []).append(doc)

    stats = {"documents": 0, "chunks": 0, "embeddings": 0, "errors": 0}

    for source_path, chunks in by_doc.items():
        first_meta = chunks[0].get("metadata", {})
        source_type = first_meta.get("source", "unknown")

        try:
            doc_row = (
                client.table("dim_document")
                .upsert(
                    {
                        "source_type": source_type,
                        "source_path": source_path,
                        "title": first_meta.get("title"),
                        "department": first_meta.get("department"),
                        "last_modified_at": first_meta.get("modified_time"),
                        "is_active": True,
                    },
                    on_conflict="source_type,source_path",
                )
                .execute()
            )
            if not doc_row.data:
                # Some client versions don't return representation on upsert; fetch explicitly.
                doc_row = (
                    client.table("dim_document")
                    .select("document_id")
                    .eq("source_type", source_type)
                    .eq("source_path", source_path)
                    .limit(1)
                    .execute()
                )
            document_id = doc_row.data[0]["document_id"]
            stats["documents"] += 1
        except Exception as e:
            logger.warning(f"[pgvector] Failed to upsert document '{source_path}': {e}")
            stats["errors"] += 1
            continue

        precomputed = [c.get("vector") for c in chunks]
        if all(v is not None for v in precomputed):
            vectors = precomputed
        else:
            texts = [c.get("text", "") for c in chunks]
            try:
                vectors = embed_texts(texts)
            except Exception as e:
                logger.warning(f"[pgvector] Embedding failed for '{source_path}': {e}")
                stats["errors"] += 1
                continue

        for chunk, vector in zip(chunks, vectors):
            meta = chunk.get("metadata", {})
            ordinal = meta.get("chunk_index", 0)
            try:
                chunk_row = (
                    client.table("fact_chunk")
                    .upsert(
                        {
                            "document_id": document_id,
                            "ordinal": ordinal,
                            "text": chunk.get("text", ""),
                            "metadata": meta,
                        },
                        on_conflict="document_id,ordinal",
                    )
                    .execute()
                )
                if not chunk_row.data:
                    chunk_row = (
                        client.table("fact_chunk")
                        .select("chunk_id")
                        .eq("document_id", document_id)
                        .eq("ordinal", ordinal)
                        .limit(1)
                        .execute()
                    )
                chunk_id = chunk_row.data[0]["chunk_id"]
                stats["chunks"] += 1

                client.table("fact_embedding").upsert(
                    {
                        "chunk_id": chunk_id,
                        "model": os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001"),
                        "dim": len(vector),
                        "embedding": vector,
                    },
                    on_conflict="chunk_id",
                ).execute()
                stats["embeddings"] += 1
            except Exception as e:
                logger.warning(f"[pgvector] Failed to upsert chunk (doc={source_path}, ordinal={ordinal}): {e}")
                stats["errors"] += 1

    return stats


# ─────────────────────────────────────────────────────────────────────────
# [OPS:PVEC-004] pgvector_search() — the actual fallback query
#
# API/CALL: Gemini embed_content (via embed_texts(), a fresh embedding —
#       not reused from the primary attempt); Postgres RPC match_chunks()
#       (SCHEMA — see [OPS:SCHEMA-003] in backend/sql/schema.sql) — a
#       cosine-similarity `<=>` scan over fact_embedding.embedding.
# NUANCE: the embedding is passed as json.dumps(query_embedding) — a TEXT
#       string, not Postgres's native VECTOR type — then cast ::vector
#       inside the SQL function body. This works around unreliable
#       PostgREST JSON-array→vector coercion when passed directly; see the
#       ::vector cast in match_chunks()'s definition for the other half of
#       this fix.
# RETURNS: [{text, score, metadata}] — the exact shape [OPS:CHAT-005]
#       _norm_one() already understands, so chat.py's retrieval code
#       treats primary and fallback results identically downstream.
# CALLED BY: [OPS:CHAT-008] _pgvector_retrieve() (via asyncio.to_thread,
#       since this function is synchronous).
# ─────────────────────────────────────────────────────────────────────────
def pgvector_search(query: str, top_k: int = 4) -> List[Dict[str, Any]]:
    """
    Real fallback retrieval via Postgres/pgvector cosine similarity, called
    when the primary enhanced_index.json path returns nothing or low-
    confidence results. Returns the same normalized shape chat.py's
    _norm_one() already understands: [{text, score, metadata}].
    """
    client = _get_service_client()
    if client is None:
        return []

    try:
        vectors = embed_texts([query])
        query_embedding = vectors[0]
    except Exception as e:
        logger.warning(f"[pgvector] Query embedding failed: {e}")
        return []

    try:
        resp = client.rpc(
            "match_chunks",
            {"query_embedding": json.dumps(query_embedding), "match_count": top_k},
        ).execute()
    except Exception as e:
        logger.warning(f"[pgvector] match_chunks RPC failed: {e}")
        return []

    results = []
    for row in resp.data or []:
        results.append(
            {
                "text": row.get("text", ""),
                "score": float(row.get("similarity") or 0.0),
                "metadata": {
                    **(row.get("metadata") or {}),
                    "title": row.get("title"),
                    "department": row.get("department"),
                    "source": row.get("source_type"),
                    "pgvector_fallback": True,
                },
            }
        )
    return results


# ─────────────────────────────────────────────────────────────────────────
# [OPS:PVEC-005] log_query() — audit-trail write, fact_query +
#                 bridge_query_citation
#
# WHAT: one fact_query row per chat request (the question, timing, token
#       counts, whether the fallback fired), plus one bridge_query_citation
#       row per cited source — re-deriving each citation's document_id/
#       chunk_id via the same (source_type, source_path) + chunk_index
#       lookup keys that [OPS:PVEC-003] upsert_documents() wrote them
#       under, so citations correctly link back even though `citations`
#       only carries denormalized text/metadata, not real foreign keys.
# CALLED BY: [OPS:CHAT-015] chat_complete(), [OPS:CHAT-020] chat_stream()
#       (inside event_generator(), after the "done" SSE event) — always
#       BEFORE [OPS:PVEC-006] upsert_query_embedding() for the same
#       query_id, so a query is logged before it becomes findable.
# BREAKS IF: fails silently and often — every DB call here is wrapped in
#       its own try/except (one per citation, not just the outer
#       function), specifically so one bad citation lookup doesn't lose
#       the fact_query row or the other citations.
# ─────────────────────────────────────────────────────────────────────────
def log_query(
    *,
    query_id: str,
    query_text: str,
    top_k: int,
    used_fallback: bool,
    retrieval_confidence: Optional[float],
    processing_time_ms: int,
    citations: List[Dict[str, Any]],
    user_id: Optional[str] = None,
    prompt_tokens: Optional[int] = None,
    completion_tokens: Optional[int] = None,
    total_tokens: Optional[int] = None,
) -> bool:
    """
    Audit logging per the spec's operational-transparency requirement:
    every chat request writes a fact_query row plus one bridge_query_citation
    row per cited source. Best-effort — logging failures never affect the
    chat response itself.

    `citations` is the same normalized doc list used to render sources:
    [{"text", "score", "metadata": {"file_name"/"drive_file_id"/...}}].
    Document/chunk identity is resolved by the same (source_type,
    source_path) key used in upsert_documents(), so citations correctly link
    back to dim_document/fact_chunk rows written during ingestion.
    """
    client = _get_service_client()
    if client is None:
        return False

    try:
        client.table("fact_query").insert(
            {
                "query_id": query_id,
                "user_id": user_id,
                "query_text": query_text,
                "top_k": top_k,
                "used_fallback": used_fallback,
                "retrieval_confidence": retrieval_confidence,
                "processing_time_ms": processing_time_ms,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
            }
        ).execute()
    except Exception as e:
        logger.warning(f"[pgvector] Failed to log fact_query: {e}")
        return False

    for rank, doc in enumerate(citations, start=1):
        meta = doc.get("metadata", {})
        source_path = _document_source_path(meta)
        source_type = meta.get("source", "unknown")
        try:
            doc_row = (
                client.table("dim_document")
                .select("document_id")
                .eq("source_type", source_type)
                .eq("source_path", source_path)
                .limit(1)
                .execute()
            )
            if not doc_row.data:
                continue
            document_id = doc_row.data[0]["document_id"]

            ordinal = meta.get("chunk_index", 0)
            chunk_row = (
                client.table("fact_chunk")
                .select("chunk_id")
                .eq("document_id", document_id)
                .eq("ordinal", ordinal)
                .limit(1)
                .execute()
            )
            if not chunk_row.data:
                continue
            chunk_id = chunk_row.data[0]["chunk_id"]

            client.table("bridge_query_citation").insert(
                {
                    "query_id": query_id,
                    "document_id": document_id,
                    "chunk_id": chunk_id,
                    "relevance_score": doc.get("score", 0.0),
                    "rank": rank,
                }
            ).execute()
        except Exception as e:
            logger.warning(f"[pgvector] Failed to log citation (rank={rank}): {e}")

    return True


# ─────────────────────────────────────────────────────────────────────────
# [OPS:PVEC-006] SIMILAR_QUERY_THRESHOLD + upsert_query_embedding() —
#                 the write half of the "similar questions" feature
#
# WHAT: 0.80 is deliberately much stricter than RAG_QUALITY_THRESHOLD's
#       0.5 [OPS:CHAT-009] — that threshold decides "is this chunk worth
#       showing as a source," this one decides "are these two *questions*
#       basically the same question," which is a much higher bar to avoid
#       the UI implying a false relationship between unrelated queries.
# CALLS: [OPS:IDX-002] embed_texts() — same shared embedding function as
#       every other embed call in the system, so a query's own vector and
#       a chunk's vector always live in the same space.
# CALLED BY: [OPS:CHAT-015]/[OPS:CHAT-020], always AFTER log_query()
#       [OPS:PVEC-005] for that same query_id — ordering matters: this is
#       what keeps a query from ever appearing in its own similar-queries
#       results (it isn't in fact_query_embedding yet when its own
#       find_similar_queries() call runs).
# ─────────────────────────────────────────────────────────────────────────
# Below this cosine-similarity score, two questions are treated as
# unrelated rather than "similar" — without a floor, match_queries() always
# returns its top-N rows even when the closest one is barely related,
# which would make the "similar questions" UI claim a relationship that
# isn't really there.
SIMILAR_QUERY_THRESHOLD = float(os.getenv("SIMILAR_QUERY_THRESHOLD", "0.80"))


def upsert_query_embedding(query_id: str, query_text: str) -> bool:
    """
    Embeds and stores a query's own text vector, so *future* queries can be
    compared against it via find_similar_queries(). Called after a query has
    already been logged via log_query() — best-effort, same as the rest of
    this module's audit-trail writes.
    """
    client = _get_service_client()
    if client is None:
        return False

    try:
        vector = embed_texts([query_text])[0]
        client.table("fact_query_embedding").upsert(
            {"query_id": query_id, "embedding": vector},
            on_conflict="query_id",
        ).execute()
        return True
    except Exception as e:
        logger.warning(f"[pgvector] Failed to store query embedding for {query_id}: {e}")
        return False


# ─────────────────────────────────────────────────────────────────────────
# [OPS:PVEC-007] find_similar_queries() — the read half of the "similar
#                 questions" feature; the real metric behind that UI
#
# API/CALL: Gemini embed_content (query's own text); Postgres RPC
#       match_queries() (SCHEMA — [OPS:SCHEMA-004]) — cosine similarity
#       over fact_query_embedding, same TEXT→::vector cast pattern as
#       match_chunks() [OPS:PVEC-004].
# WHAT MAKES THIS A REAL METRIC, NOT A PLACEHOLDER: similarity is an
#       actual cosine-similarity score against genuinely-logged prior
#       questions, filtered by SIMILAR_QUERY_THRESHOLD [OPS:PVEC-006] —
#       not a random/fabricated number. Returns [] (not a fake low
#       number) whenever there's truly nothing to compare against.
# CALLED BY: [OPS:CHAT-015] chat_complete(), [OPS:CHAT-020] chat_stream()
#       — the result becomes the "similar_queries" field in
#       ChatResponse / the SSE "meta" event, rendered by the
#       SimilarQuestions component [OPS:FE-CHAT].
# ─────────────────────────────────────────────────────────────────────────
def find_similar_queries(
    query_text: str, top_k: int = 5, exclude_query_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Finds prior questions genuinely similar to this one — a real "people are
    also asking" signal backed by cosine similarity over actually-logged
    queries, not a placeholder number. Returns [] whenever there's nothing
    to compare against yet (empty history, Supabase not configured, or no
    match clears SIMILAR_QUERY_THRESHOLD) rather than a misleading result.
    """
    client = _get_service_client()
    if client is None:
        return []

    try:
        vector = embed_texts([query_text])[0]
    except Exception as e:
        logger.warning(f"[pgvector] Similar-query embedding failed: {e}")
        return []

    try:
        resp = client.rpc(
            "match_queries",
            {
                "query_embedding": json.dumps(vector),
                "match_count": top_k,
                "exclude_query_id": exclude_query_id,
            },
        ).execute()
    except Exception as e:
        logger.warning(f"[pgvector] match_queries RPC failed: {e}")
        return []

    results = []
    for row in resp.data or []:
        similarity = float(row.get("similarity") or 0.0)
        if similarity < SIMILAR_QUERY_THRESHOLD:
            continue
        results.append(
            {
                "query_text": row.get("query_text", ""),
                "similarity": similarity,
                "created_at": row.get("created_at"),
            }
        )
    return results


# ─────────────────────────────────────────────────────────────────────────
# [OPS:PVEC-008] set_feedback() — thumbs up/down write
#
# WHAT: a single UPDATE on fact_query.user_rating keyed by query_id.
#       `rating` is validated as exactly "up"/"down" upstream by
#       FeedbackRequest's Literal type [OPS:CHAT-002] — this function
#       trusts the caller rather than re-validating.
# CALLED BY: [OPS:CHAT-021] submit_feedback() — the POST /feedback route.
# ─────────────────────────────────────────────────────────────────────────
def set_feedback(query_id: str, rating: str) -> bool:
    """
    Records a thumbs up/down on a previously-answered query by updating its
    fact_query row. `rating` is "up" or "down" — validated by the caller
    (chat.py's request model), not here. Best-effort like the rest of this
    module: a Supabase outage shouldn't turn a UI button click into a 500.
    """
    client = _get_service_client()
    if client is None:
        return False

    try:
        client.table("fact_query").update({"user_rating": rating}).eq(
            "query_id", query_id
        ).execute()
        return True
    except Exception as e:
        logger.warning(f"[pgvector] Failed to record feedback for {query_id}: {e}")
        return False


# ─────────────────────────────────────────────────────────────────────────
# [OPS:PVEC-009] hydrate_index_from_supabase() — rebuild enhanced_index.json
#                 from Supabase, no Drive re-scan, no re-embedding
#
# WHY THIS EXISTS: Render's free tier has ephemeral local disk — every
#       restart/redeploy wipes enhanced_index.json off disk. Because
#       [OPS:PVEC-003] upsert_documents() already dual-writes every chunk
#       + embedding to Supabase at ingest time, the full JSON index is
#       reconstructable purely from Postgres — no need to hit Google
#       Drive or pay for re-embedding just because a process restarted.
#       Verified for real this session by deleting the local index file
#       and confirming automatic rebuild on the next startup.
# MECHANICS: paginates fact_chunk (500 rows/page) joined to
#       fact_embedding, reassembles the exact {"dim", "items": [{id,
#       text, metadata, vector}]} shape [OPS:IDX-003]
#       PersistedInMemorySearch._load_if_exists() expects for its legacy
#       format branch.
# CALLED BY: main.py's lifespan startup [OPS:MAIN-002] — only when no
#       local index file exists yet; returns None (not an empty dict) so
#       the caller can distinguish "nothing to hydrate" from "hydrated an
#       empty index."
# ─────────────────────────────────────────────────────────────────────────
def hydrate_index_from_supabase() -> Optional[Dict[str, Any]]:
    """
    Rebuild the enhanced_index.json contents (the {"dim", "items"} shape
    PersistedInMemorySearch reads) directly from Supabase, without touching
    Google Drive or re-embedding anything.

    Exists specifically for platforms with ephemeral local disk (e.g. Render
    on restart/redeploy): since every chunk + embedding is already
    dual-written to Supabase at ingest time, the JSON index is fully
    reconstructable from there — no need to re-scan Drive just because a
    process restart wiped the local file.

    Returns None if Supabase isn't configured or there's nothing to hydrate;
    the caller (main.py's startup) falls back to its existing "no index yet"
    behavior in that case.
    """
    client = _get_service_client()
    if client is None:
        return None

    items: List[Dict[str, Any]] = []
    page_size = 500
    offset = 0

    try:
        while True:
            resp = (
                client.table("fact_chunk")
                .select("chunk_id, text, metadata, fact_embedding(embedding)")
                .range(offset, offset + page_size - 1)
                .execute()
            )
            rows = resp.data or []
            if not rows:
                break

            for row in rows:
                embedding_rows = row.get("fact_embedding")
                if isinstance(embedding_rows, list):
                    embedding_row = embedding_rows[0] if embedding_rows else None
                else:
                    embedding_row = embedding_rows
                if not embedding_row:
                    continue

                raw_vector = embedding_row.get("embedding")
                vector = json.loads(raw_vector) if isinstance(raw_vector, str) else raw_vector
                if not vector:
                    continue

                items.append(
                    {
                        "id": row["chunk_id"],
                        "text": row.get("text", ""),
                        "metadata": row.get("metadata") or {},
                        "vector": vector,
                    }
                )

            if len(rows) < page_size:
                break
            offset += page_size
    except Exception as e:
        logger.warning(f"[pgvector] Failed to hydrate index from Supabase: {e}")
        return None

    if not items:
        return None

    return {"dim": len(items[0]["vector"]), "items": items}
