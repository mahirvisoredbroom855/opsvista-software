"""
This file is OpsVista's second, backup place to search for an answer —
a copy of the same document data, but stored in the Supabase database
instead of a local file. It only gets used when the fast local search
isn't confident enough. This file also writes the permanent record of
every question ever asked (for the dashboard), and stores thumbs
up/down feedback.

backend/app/features/rag_chatbot/vector/pgvector_store.py

MODULE: [OPS:PVEC] — the pgvector fallback + audit-trail layer

What it does: a second retrieval path (pgvector_search) that only
fires when the primary in-memory index comes up empty or
low-confidence, plus the audit-trail writes (log_query,
upsert_query_embedding, set_feedback) that make the similar-questions
feature and the /feedback endpoint real, not stubs.

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
# What it does: builds a Supabase client using the service-role key,
# which bypasses Row Level Security (contrast with the public anon-key
# client in auth_deps.py, which enforces it). Every other function in
# this file calls this itself rather than taking a client as an
# argument. If SUPABASE_URL or the service key is missing, this
# returns None instead of raising — which is what lets every function
# in this file degrade gracefully instead of crashing when Supabase
# isn't configured yet.
#
# Called by: every other function in this file; is_configured() is
# also used directly by GET /status in chat.py.
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
# What it does: builds one consistent ID for a document regardless of
# where it came from. Drive files use their permanent drive_file_id;
# local test documents use "owner_folder/file_name" instead, since
# they have no Drive ID. upsert_documents() writes rows keyed on this
# exact value, and log_query() re-derives the same value later to link
# citations back to the right document — the two must always agree or
# citations silently fail to match.
# ─────────────────────────────────────────────────────────────────────────
def _document_source_path(metadata: Dict[str, Any]) -> str:
    """Stable unique key for a document, independent of source (Drive vs local)."""
    if metadata.get("drive_file_id"):
        return str(metadata["drive_file_id"])
    return f"{metadata.get('owner_folder', '')}/{metadata.get('file_name', 'unknown')}"


# ─────────────────────────────────────────────────────────────────────────
# [OPS:PVEC-003] upsert_documents() — the dual-write path
#
# What it does: writes chunk data into three Supabase tables —
# dim_document, fact_chunk, fact_embedding. If a chunk already has a
# precomputed embedding vector (because the JSON index just embedded
# it moments ago), this reuses that exact vector instead of asking
# Gemini to embed it again — otherwise every reindex would silently
# double the embedding API cost.
#
# Called by: build_local_index.py and build_drive_index.py, right
# after the JSON index is (re)built, so pgvector's data never drifts
# out of sync with enhanced_index.json.
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
# What it does: embeds the question fresh (not reused from the primary
# attempt), then calls a database function called match_chunks() —
# defined in backend/sql/schema.sql — which does a cosine-similarity
# comparison directly inside Postgres. The embedding is sent as a text
# string, not a native vector type, because that's the reliable way to
# pass it through Supabase's REST layer; match_chunks() casts it back
# to a real vector on the database side.
#
# Returns: [{text, score, metadata}] — the exact shape _norm_one() in
# chat.py already understands, so primary and fallback results are
# treated identically downstream.
#
# Called by: _pgvector_retrieve() in chat.py, on a background thread
# (this function itself is synchronous).
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
# What it does: writes one row to fact_query per chat request (the
# question, timing, whether the backup search fired), plus one row to
# bridge_query_citation per cited source. It re-looks-up each
# citation's real document_id/chunk_id using the same identity key
# upsert_documents() wrote them under, since the citation data passed
# in only carries text/metadata, not real foreign keys. Every database
# call here has its own try/except, so one bad citation lookup can't
# lose the main fact_query row or the other citations.
#
# Called by: chat_complete(), chat_stream() — always BEFORE
# upsert_query_embedding() for the same query, so a question can never
# match itself in a future similar-questions search.
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
# What it does: 0.80 is a much stricter bar than the 0.5 used to
# decide "is this document chunk relevant" — this one decides "are
# these two questions basically the same question," which needs a
# much higher bar so the UI never implies a relationship between
# unrelated questions. upsert_query_embedding() embeds the question's
# own text (using the exact same shared embedding function as every
# other embed call, so it lives in the same vector space as document
# chunks) and stores it for future comparisons.
#
# Called by: chat_complete()/chat_stream(), always AFTER log_query()
# for the same question — that ordering is what keeps a question from
# ever matching itself.
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
# What it does: embeds the current question, then calls a database
# function (match_queries()) that finds prior questions closest to it
# by cosine similarity, filtered by SIMILAR_QUERY_THRESHOLD. This is a
# real, live comparison against genuinely-logged questions — not a
# placeholder number — and returns an empty list rather than a
# misleading one whenever there's truly nothing similar yet.
#
# Called by: chat_complete(), chat_stream() — the result becomes the
# "similar_queries" field the frontend renders as "people also asked."
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
# What it does: one UPDATE on fact_query.user_rating for a given
# query_id. Trusts the caller to have already validated `rating` as
# "up" or "down" (ChatRequest's Literal type in chat.py handles that).
#
# Called by: submit_feedback() — the POST /feedback route.
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
# What it does: this exists because Render's free tier wipes local
# disk on every restart — but every chunk and embedding was already
# dual-written to Supabase at ingest time, so the whole local JSON
# index file can be rebuilt purely by reading it back out of Postgres,
# no need to touch Google Drive or pay for re-embedding. It pages
# through fact_chunk (500 rows at a time) joined to fact_embedding,
# and reassembles the exact {"dim", "items"} shape the local index
# file expects.
#
# Called by: main.py's boot-time startup check, only when no local
# index file exists yet. Returns None (not an empty dict) so the
# caller can tell "nothing to hydrate" apart from "hydrated, but empty."
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
