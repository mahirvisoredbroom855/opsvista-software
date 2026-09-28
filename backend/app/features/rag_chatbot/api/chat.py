# backend/app/features/rag_chatbot/api/chat.py
#
# ═══════════════════════════════════════════════════════════════════════════
# MODULE: [OPS:CHAT] — the core request path
#
# This file owns everything from "a question arrived over HTTP" to "an
# answer, its citations, and its audit-log row all exist." Every tagged
# comment block below is independently findable — grep "OPS:CHAT-0NN" (or
# ask for it by number) and you land exactly there, in this file or any
# other, since the same numbering scheme is used project-wide.
#
# The three things this file is actually orchestrating, in order:
#   1. RETRIEVAL   — find the right document chunks (dual-path: primary
#                    in-memory index, pgvector fallback on low confidence)
#   2. GENERATION  — hand those chunks to an LLM, get an answer back
#                    (blocking for /complete, streamed for /stream)
#   3. AUDIT        — log the interaction to Supabase, best-effort, never
#                    blocking the response even if logging itself fails
#
# See also: docs/CODE_INDEX.md for the full project-wide tag list;
# README.md § Architecture for the diagram this file implements.
# ═══════════════════════════════════════════════════════════════════════════
from __future__ import annotations

import os
import json
import uuid
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple

from fastapi import APIRouter, Query, Body, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.auth_deps import get_current_user_optional
from app.core.rate_limit import limiter

router = APIRouter(prefix="/api/rag/chat", tags=["RAG Chat"])

# =========================
# Request / Response Models
# =========================

# ─────────────────────────────────────────────────────────────────────────
# [OPS:CHAT-001] ChatRequest — the body shape for POST /complete and /stream
#
# WHAT: message = the user's question (raw text, no preprocessing expected
#       from the client). top_k = how many chunks to retrieve (default 4 —
#       matches the "N sources" the frontend renders). debug = when true,
#       chat_complete() prefixes the response with raw error text instead
#       of hiding it behind a generic fallback message.
# VALIDATED BY: FastAPI/Pydantic automatically, before chat_complete() or
#       chat_stream() ever runs — a malformed body never reaches this code.
# USED BY: [OPS:CHAT-015] chat_complete(), [OPS:CHAT-020] chat_stream()
# ─────────────────────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str
    top_k: int = 4
    debug: bool = False

# ─────────────────────────────────────────────────────────────────────────
# [OPS:CHAT-002] FeedbackRequest — the body shape for POST /feedback
#
# WHAT: query_id must be a chat_id returned by an earlier /complete or
#       /stream call (the frontend gets it from the SSE "meta"/"done"
#       events). rating is constrained to exactly "up"/"down" by the
#       Literal type — anything else is rejected before submit_feedback()
#       runs, same validation-for-free pattern as ChatRequest above.
# USED BY: [OPS:CHAT-021] submit_feedback()
# WRITES TO: fact_query.user_rating via [OPS:PVEC-008] set_feedback()
# ─────────────────────────────────────────────────────────────────────────
class FeedbackRequest(BaseModel):
    query_id: str
    rating: Literal["up", "down"]

class RetrieveResponse(BaseModel):
    count: int
    trace: Dict[str, Any]
    results: List[Dict[str, Any]]
    query: str
    top_k: int
    use_fake: bool

# ─────────────────────────────────────────────────────────────────────────
# [OPS:CHAT-004] ChatResponse — the body shape returned by POST /complete
#
# WHAT: this is the single-JSON-response shape (as opposed to /stream's
#       SSE events, which carry the same fields split across meta/done).
#       trace is the dual-path retrieval trace (see [OPS:CHAT-010]) —
#       exposing it here is what makes the frontend's TracePanel possible.
#       similar_queries defaults to [] rather than being omitted, so the
#       frontend never has to special-case "field missing" vs "genuinely
#       no similar questions yet" — both render as an empty array.
# SEE ALSO: README § API Reference → Response shape (/complete)
# ─────────────────────────────────────────────────────────────────────────
class ChatResponse(BaseModel):
    chat_id: str
    content: str
    model: str
    sources: List[Dict[str, Any]]
    created: str
    usage: Dict[str, Any]
    trace: Dict[str, Any]
    warnings: List[str] = []
    similar_queries: List[Dict[str, Any]] = []


# =========================
# Utilities (paths & normalize)
# =========================

def _vector_dir() -> Path:
    # api/chat.py -> rag_chatbot/ -> vector/
    return Path(__file__).resolve().parents[1] / "vector"

def _safe_float(x: Any) -> float:
    try:
        return float(x)
    except Exception:
        return 0.0

# ─────────────────────────────────────────────────────────────────────────
# [OPS:CHAT-005] _norm_one() — the shape-normalizer both retrieval paths
#                 funnel through
#
# WHAT: the primary index ([OPS:IDX-005] search()) and the pgvector
#       fallback ([OPS:PVEC-004] pgvector_search()) return results in
#       *different native shapes* (one's a Python dict from an in-memory
#       search, the other's a row from a Postgres RPC response) — this
#       function is what makes the rest of chat.py able to treat both
#       paths identically afterward, via one common {text, score,
#       metadata} shape.
# WHY IT'S THIS DEFENSIVE: handles dict/tuple/object inputs and several
#       field-name conventions (score vs similarity vs relevance) because
#       this predates the current two-source-only reality and was written
#       to tolerate whatever shape a search backend happened to return.
# CALLED BY: [OPS:CHAT-007] _enhanced_retrieve(), [OPS:CHAT-008]
#       _pgvector_retrieve() — once per raw result row.
# ─────────────────────────────────────────────────────────────────────────
def _norm_one(record: Any) -> Dict[str, Any]:
    """
    Normalize heterogeneous search results into a single shape:
    {text, score, metadata}
    Supports dicts/tuples/objects; pulls from 'snippet' if 'text' missing.
    """
    # dict-like
    if isinstance(record, dict):
        text = (
            record.get("text")
            or record.get("snippet")          # many search layers return this
            or record.get("chunk")
            or record.get("content")
            or record.get("page_content")
            or ""
        )
        # accept different score field conventions
        score = _safe_float(
            record.get("score")
            or (record.get("scores") or {}).get("final_score", 0.0)
            or record.get("similarity")
            or record.get("relevance")
            or 0.0
        )
        metadata = record.get("metadata", {}) or {}

        # promote helpful top-level fields into metadata
        for k in (
            "document_id", "file_name", "document_type", "department",
            "chunk_index", "path", "source", "id", "created_at"
        ):
            if k in record and k not in metadata:
                metadata[k] = record[k]
        # handle nested {"document": {...}}
        if not text and isinstance(record.get("document"), dict):
            d = record["document"]
            text = d.get("text") or d.get("content") or d.get("page_content") or text
            metadata = d.get("metadata", metadata)
        return {"text": text, "score": score, "metadata": metadata}

    # tuple/list like (doc, score) or (text, score, meta)
    if isinstance(record, (tuple, list)):
        if len(record) == 2:
            doc, score = record
            if isinstance(doc, dict):
                base = _norm_one(doc)
                base["score"] = _safe_float(score)
                return base
            return {"text": str(doc), "score": _safe_float(score), "metadata": {}}
        if len(record) >= 3:
            text, score, meta = record[0], record[1], record[2]
            return {"text": str(text), "score": _safe_float(score), "metadata": meta if isinstance(meta, dict) else {}}

    # object-like
    text = (
        getattr(record, "text", None)
        or getattr(record, "snippet", None)
        or getattr(record, "content", None)
        or getattr(record, "page_content", None)
        or ""
    )
    score = _safe_float(getattr(record, "score", 0.0))
    metadata = getattr(record, "metadata", {}) or {}
    return {"text": text, "score": score, "metadata": metadata}


# =========================
# Enhanced Index Search (Primary)
# =========================

# ─────────────────────────────────────────────────────────────────────────
# [OPS:CHAT-006] _get_enhanced_index() — loads/constructs the primary
#                 in-memory search instance for this request
#
# WHAT: picks the index JSON file to use (RAG_INDEX_PATH env var, else
#       the first of several fallback filenames that actually exists on
#       disk), peeks at its embedding_dim to decide USE_MOCK_EMBEDDINGS,
#       then constructs a fresh PersistedInMemorySearch [OPS:IDX-003]
#       around it.
# NUANCE: this reloads/re-reads the index file on *every call* rather
#       than caching a singleton — fine at the current corpus size
#       (~117 chunks, loads in well under a second), but worth knowing
#       if latency profiling ever points here at a much larger corpus.
# CALLED BY: [OPS:CHAT-007] _enhanced_retrieve(), once per request.
# ─────────────────────────────────────────────────────────────────────────
def _get_enhanced_index():
    """Get enhanced index search instance."""
    from ..vector.persisted_inmemory_search import PersistedInMemorySearch

    vdir = _vector_dir()
    env_path = os.getenv("RAG_INDEX_PATH")

    candidates: List[Path] = []
    if env_path:
        candidates.append(Path(env_path))

    # Prefer enhanced_index.json (your embedded Google Drive data)
    candidates += [
        vdir / "enhanced_index.json",  # <- your 1536-dim file with Google Drive data
        vdir / "index.json",
        vdir / ".index.json",
        vdir / "demo_index.json",
    ]

    idx_path = next((p for p in candidates if p and p.exists()), candidates[0])

    # Align embedding settings to the index metadata
    try:
        meta = json.loads(Path(idx_path).read_text(encoding="utf-8"))
        dim = int(meta.get("embedding_dim") or meta.get("dim") or 0)
        model = meta.get("embedding_model") or "text-embedding-3-small"
        if dim == 384:
            os.environ["USE_MOCK_EMBEDDINGS"] = "true"
        elif dim == 1536:
            os.environ["USE_MOCK_EMBEDDINGS"] = "false"
            os.environ.setdefault("OPENAI_EMBEDDING_MODEL", model)
    except Exception:
        pass

    os.environ["RAG_INDEX_PATH"] = str(idx_path)
    return PersistedInMemorySearch(index_path=idx_path)

# ─────────────────────────────────────────────────────────────────────────
# [OPS:CHAT-007] _enhanced_retrieve() — the PRIMARY retrieval path
#
# API/CALL: none directly to an external API — delegates to
#       [OPS:IDX-005] PersistedInMemorySearch.search(), which itself
#       calls Gemini's embed API once (to embed the question) before
#       doing an in-memory cosine-similarity scan against every chunk.
# RETURNS: (docs, trace) — docs is a list of {text, score, metadata},
#       trace records which implementation answered and how many results
#       came back, for observability (see the "trace" object in
#       [OPS:CHAT-010]).
# BREAKS IF: the index file is missing/corrupt — caught explicitly and
#       turned into an empty-results trace with impl="failed" rather than
#       raising, so a bad index degrades gracefully instead of 500ing.
# CALLED BY: [OPS:CHAT-010] retrieve_with_trace(), always first.
# ─────────────────────────────────────────────────────────────────────────
def _enhanced_retrieve(q: str, top_k: int) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Primary retrieval using enhanced index."""
    index = _get_enhanced_index()
    try:
        results = index.search(q, top_k=top_k)
    except Exception as e:
        return [], {"impl": "failed", "method": "enhanced_index_search", "error": str(e)}

    docs = [_norm_one(r) for r in (results or [])]
    trace = {
        "impl": "enhanced_index",
        "method": "persisted_inmemory_search",
        "count": len(docs),
        "index_path": str(getattr(index, "index_path", "?")),
        "dim": int(getattr(index, "dim", None) or 0),
    }
    return docs, trace


# =========================
# pgvector retrieval (real fallback path — Supabase/Postgres)
# =========================

# ─────────────────────────────────────────────────────────────────────────
# [OPS:CHAT-008] _pgvector_retrieve() — the FALLBACK retrieval path
#
# API/CALL: [OPS:PVEC-004] pgvector_search() — which itself calls
#       Gemini's embed API a second time (the question gets re-embedded
#       independently here, not reused from the primary attempt) and
#       then calls Postgres's match_chunks() RPC (SCHEMA — see
#       backend/sql/schema.sql).
# WHY asyncio.to_thread: supabase-py's client is synchronous; running it
#       directly inside this async function would block the event loop
#       for every other in-flight request while waiting on the network
#       call. to_thread() runs it on a worker thread instead.
# DEGRADES TO: [] (empty list) + an "error" field in trace, whenever
#       Supabase isn't configured or the RPC fails — never raises, so a
#       misconfigured/unreachable Supabase never breaks the primary path.
# CALLED BY: [OPS:CHAT-010] retrieve_with_trace(), only when the primary
#       path's confidence is too low or empty — see the two-condition
#       gate documented there.
# ─────────────────────────────────────────────────────────────────────────
async def _pgvector_retrieve(q: str, top_k: int) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Real fallback retrieval via Postgres/pgvector cosine similarity search
    (see backend/sql/schema.sql and vector/pgvector_store.py). This is the
    dual-path design's actual second path — not a stub — but it degrades
    gracefully to "no results" if Supabase isn't configured yet.
    """
    from ..vector.pgvector_store import is_configured, pgvector_search

    if not is_configured():
        return [], {"impl": "pgvector", "method": "match_chunks", "error": "Supabase not configured"}

    try:
        results = await asyncio.to_thread(pgvector_search, q, top_k)
    except Exception as e:
        return [], {"impl": "pgvector", "method": "match_chunks", "error": str(e)}

    docs = [_norm_one(r) for r in results]
    return docs, {"impl": "pgvector", "method": "match_chunks", "count": len(docs)}


# =========================
# Quality gate helpers
# =========================

# ─────────────────────────────────────────────────────────────────────────
# [OPS:CHAT-009] Quality-gate helpers — RAG_QUALITY_THRESHOLD,
#                 _retrieval_confidence(), _source_diversity()
#
# WHAT: three small pieces that together decide "was that a GOOD result,
#       not just A result." RAG_QUALITY_THRESHOLD (default 0.5, env-
#       overridable) is the confidence floor below which the primary
#       path is treated as untrustworthy even though it returned
#       something. _retrieval_confidence() is just the single best
#       score among the results — a proxy for confidence, not a
#       calibrated probability (worth being precise about this distinction
#       if asked). _source_diversity() is the fraction of results coming
#       from distinct files — a low value is a legitimate outcome (one
#       document genuinely dominates), but the spec calls for surfacing
#       it, not hiding it.
# BREAKS IF: RAG_QUALITY_THRESHOLD set too high → fallback fires on nearly
#       every request (extra Supabase round-trip + latency every time).
#       Set too low → the quality gate stops doing anything meaningful,
#       weak primary answers ship without a second opinion.
# USED BY: [OPS:CHAT-010] retrieve_with_trace().
# ─────────────────────────────────────────────────────────────────────────
# Below this top-score, the enhanced index result is treated as low-
# confidence and the pgvector fallback is attempted too — not just on
# literally zero results. Configurable since "good enough" varies by corpus.
RAG_QUALITY_THRESHOLD = float(os.getenv("RAG_QUALITY_THRESHOLD", "0.5"))


def _retrieval_confidence(docs: List[Dict[str, Any]]) -> float:
    return max((d.get("score", 0.0) for d in docs), default=0.0)


def _source_diversity(docs: List[Dict[str, Any]]) -> float:
    """Fraction of results that come from distinct source files — a low
    value (many chunks, one file) is a legitimate result, but worth
    surfacing in the trace per the spec's 'diversity metrics' requirement."""
    if not docs:
        return 0.0
    files = {d.get("metadata", {}).get("file_name") for d in docs}
    return round(len(files) / len(docs), 2)


# =========================
# Main retrieve function - dual-path (Enhanced Index primary, pgvector fallback)
# =========================

# ─────────────────────────────────────────────────────────────────────────
# [OPS:CHAT-010] retrieve_with_trace() — THE dual-path retrieval
#                 entrypoint (the single most important function to be
#                 able to explain in this whole codebase)
#
# WHAT: tries [OPS:CHAT-007] _enhanced_retrieve() first, always. Falls
#       back to [OPS:CHAT-008] _pgvector_retrieve() when EITHER of two
#       conditions is true:
#         (a) the primary path returned zero results, OR
#         (b) the primary path's top confidence is below
#             RAG_QUALITY_THRESHOLD [OPS:CHAT-009] — a "successful but
#             weak" result is treated the same as no result.
#       If the fallback finds something, its results *replace* the
#       primary's entirely (not merged) and the trace records exactly
#       why the fallback fired (fallback_reason). If the fallback also
#       comes up empty, the primary's (weak) results are kept anyway —
#       something beats nothing — and the trace notes the attempt+failure.
# RETURNS: (docs, trace) — trace is what the frontend's TracePanel
#       renders directly (impl, used_fallback, retrieval_confidence,
#       source_diversity).
# CALLED BY: [OPS:CHAT-011] retrieve_endpoint() (debug endpoint),
#       [OPS:CHAT-015] chat_complete(), [OPS:CHAT-020] chat_stream()
#       (inside event_generator()) — every entry point into retrieval
#       goes through this one function, so the quality-gate logic only
#       has to be correct in one place.
# TESTED BY: backend/tests/test_chat_quality_gate.py — with
#       _enhanced_retrieve/_pgvector_retrieve monkeypatched, so these
#       tests exercise the branching logic without touching a real
#       index or Supabase.
# ─────────────────────────────────────────────────────────────────────────
async def retrieve_with_trace(q: str, top_k: int = 4, force_fake: bool = False):
    """
    Dual-path retrieval: Enhanced Index (JSON, primary) first; the pgvector
    fallback (Supabase/Postgres) activates when the primary path returns
    nothing OR its top confidence is below RAG_QUALITY_THRESHOLD — not just
    on a hard empty-results check, per the spec's "quality gate: threshold +
    diversity check" requirement.
    """
    docs, trace = _enhanced_retrieve(q, top_k)
    confidence = _retrieval_confidence(docs)
    trace["retrieval_confidence"] = confidence
    trace["source_diversity"] = _source_diversity(docs)
    trace["used_fallback"] = False

    needs_fallback = (not docs) or confidence < RAG_QUALITY_THRESHOLD
    if needs_fallback and not force_fake:
        fdocs, ftrace = await _pgvector_retrieve(q, top_k)
        if fdocs:
            ftrace["retrieval_confidence"] = _retrieval_confidence(fdocs)
            ftrace["source_diversity"] = _source_diversity(fdocs)
            ftrace["used_fallback"] = True
            ftrace["fallback_reason"] = (
                "no_primary_results" if not docs else f"low_confidence ({confidence:.2f} < {RAG_QUALITY_THRESHOLD})"
            )
            ftrace["primary_trace"] = trace
            return fdocs, ftrace
        else:
            trace["fallback_attempted"] = True
            trace["fallback_error"] = ftrace.get("error", "no pgvector results")

    if not docs:
        trace["warning"] = "No results found in enhanced index or pgvector fallback"
    return docs, trace


# =========================
# Routes
# =========================

# ─────────────────────────────────────────────────────────────────────────
# [OPS:CHAT-011] GET /_retrieve — debug endpoint, retrieval only, no LLM
#
# WHAT: exposes retrieve_with_trace() [OPS:CHAT-010] directly over HTTP,
#       with a use_fake flag that forces force_fake=True (skips the
#       fallback branch entirely) — useful for inspecting exactly what
#       the primary index alone would return, without a second Supabase
#       round-trip in the way.
# RATE LIMIT: 30/minute (via @limiter.limit, see [OPS:RATE-001]).
# ─────────────────────────────────────────────────────────────────────────
@router.get("/_retrieve", response_model=RetrieveResponse)
@limiter.limit("30/minute")
async def retrieve_endpoint(
    request: Request,
    q: str = Query(..., alias="q"),
    top_k: int = Query(4),
    use_fake: bool = Query(False),
):
    docs, trace = await retrieve_with_trace(q, top_k=top_k, force_fake=use_fake)
    return {
        "count": len(docs),
        "trace": trace,
        "results": docs,
        "query": q,
        "top_k": top_k,
        "use_fake": use_fake,
    }

# ─────────────────────────────────────────────────────────────────────────
# [OPS:CHAT-012] _render_sources() — shapes retrieved docs into the
#                 citation objects the frontend actually renders
#
# WHAT: truncates to `limit` (== body.top_k), and appends "(Google Drive)"
#       to the display label when the source is a real Drive file — this
#       is purely presentational, distinct from _build_context_texts()
#       [OPS:CHAT-013] which shapes the *same* docs for the LLM prompt.
# CONSUMED BY (frontend): the sources[] array in the "meta" SSE event and
#       the ChatResponse.sources field — rendered by SourceCard /
#       SourcesToggle in page.tsx [OPS:FE-CHAT].
# ─────────────────────────────────────────────────────────────────────────
def _render_sources(docs: List[Dict[str, Any]], limit: int = 4) -> List[Dict[str, Any]]:
    out = []
    for d in docs[:limit]:
        metadata = d.get("metadata", {})

        # Determine source display
        source_display = metadata.get("file_name", "Unknown Document")
        if metadata.get("source") == "google_drive":
            source_display += " (Google Drive)"

        out.append({
            "text": d.get("text", ""),
            "score": d.get("score", 0.0),
            "metadata": metadata,
            "source_display": source_display
        })
    return out

def _build_context_texts(docs: List[Dict[str, Any]]) -> List[str]:
    """
    Format each retrieved chunk with a header carrying its real identity
    (title, department, source) so the model can naturally refer to it by
    name instead of needing an abstract citation marker.
    """
    out = []
    for d in docs:
        metadata = d.get("metadata", {})
        title = metadata.get("title") or metadata.get("file_name", "Untitled document")
        department = metadata.get("department", "General")
        origin = "Google Drive" if metadata.get("source") == "google_drive" else "Local"
        header = f"Document: {title} | Department: {department} | Source: {origin}"
        out.append(f"{header}\n{d.get('text', '')[:1200]}")
    return out


# =========================
# Token budget enforcement
# =========================

# ─────────────────────────────────────────────────────────────────────────
# [OPS:CHAT-014] Token budget — CHARS_PER_TOKEN_ESTIMATE,
#                 MAX_CONTEXT_TOKENS, _estimate_tokens(),
#                 _enforce_token_budget()
#
# WHAT: a soft ceiling (default 6000 tokens, env-overridable) on how much
#       retrieved context gets sent to the LLM in one prompt. Chunks
#       arrive already sorted best-to-worst by relevance score, so the
#       greedy keep-until-budget-exhausted loop naturally drops the
#       *least* relevant chunks first when something has to give.
# WHY 4 CHARS/TOKEN: a rough English-text heuristic, deliberately not
#       using a real tokenizer library — tiktoken is OpenAI-specific and
#       wouldn't match Gemini's actual tokenizer anyway, so a precise
#       count would be precisely wrong for half the possible providers.
# EDGE CASE HANDLED: a single chunk alone bigger than the whole budget
#       gets hard-truncated (kept partially) rather than dropped entirely
#       — some context beats none.
# BREAKS IF: MAX_CONTEXT_TOKENS set too low → context gets aggressively
#       cut, "warnings" fills up with truncation notices, answer quality
#       degrades. Too high → risk of exceeding the LLM's actual context
#       window, which this soft budget is specifically meant to prevent.
# USED BY: [OPS:CHAT-015] chat_complete(), [OPS:CHAT-020] chat_stream().
# TESTED BY: backend/tests/test_chat_quality_gate.py.
# ─────────────────────────────────────────────────────────────────────────
# 4 chars/token is a standard rough estimate for English text — good enough
# for a soft context budget without adding a tokenizer dependency (tiktoken
# is OpenAI-specific and wouldn't match Gemini's tokenizer anyway).
CHARS_PER_TOKEN_ESTIMATE = 4
MAX_CONTEXT_TOKENS = int(os.getenv("MAX_CONTEXT_TOKENS", "6000"))


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // CHARS_PER_TOKEN_ESTIMATE)


def _enforce_token_budget(context_texts: List[str], max_tokens: int = MAX_CONTEXT_TOKENS) -> Tuple[List[str], bool]:
    """
    context_texts is already ordered best-to-worst by relevance (docs are
    sorted by score during retrieval). Greedily keep chunks until the
    estimated budget is exhausted, dropping the least-relevant remainder —
    never silently truncating the model's *answer*, only how much source
    context it gets to see. Returns (kept_texts, was_truncated).
    """
    kept: List[str] = []
    total = 0
    truncated = False

    for text in context_texts:
        t = _estimate_tokens(text)
        if not kept and t > max_tokens:
            # Single chunk alone exceeds the whole budget: hard-truncate it
            # rather than dropping it entirely (still gives partial context).
            allowed_chars = max(200, max_tokens * CHARS_PER_TOKEN_ESTIMATE)
            kept.append(text[:allowed_chars])
            total = max_tokens
            truncated = True
            continue
        if total + t > max_tokens:
            truncated = True
            continue
        kept.append(text)
        total += t

    return kept, truncated

# ─────────────────────────────────────────────────────────────────────────
# [OPS:CHAT-015] POST /complete — the non-streaming chat endpoint (the
#                 "original" endpoint; [OPS:CHAT-020] /stream is the
#                 later SSE upgrade with the same underlying pipeline)
#
# FULL FLOW, IN ORDER:
#   1. [OPS:CHAT-010] retrieve_with_trace() — dual-path retrieval
#   2. warnings[] populated based on what happened (empty/fallback/
#      fallback-also-empty) — this is what the frontend surfaces as
#      user-visible caveats, not hidden in a log only.
#   3. [OPS:PVEC-007] find_similar_queries() — best-effort, wrapped in
#      try/except so a Supabase hiccup here can never break the answer.
#   4. LLM call via [OPS:LLM-003] LLMClient.complete_with_messages() —
#      on failure, falls back to literally showing the raw retrieved
#      text instead of nothing (see the except block below).
#   5. Response assembled into the ChatResponse [OPS:CHAT-004] shape.
#   6. Audit logging: [OPS:PVEC-005] log_query() then [OPS:PVEC-006]
#      upsert_query_embedding() — logging happens BEFORE the embedding
#      write specifically so this exact query can never match itself in
#      a future similar-queries lookup.
# API/CALL: Gemini generate_content (via LLMClient), Gemini embed_content
#       (via retrieval + find_similar_queries), Supabase REST (via
#       log_query/upsert_query_embedding).
# RATE LIMIT: 20/minute.
# AUTH: optional — Depends(get_current_user_optional) [OPS:AUTH-001]
#       means an anonymous request still gets an answer; user_id is just
#       None on the logged row in that case.
# ─────────────────────────────────────────────────────────────────────────
@router.post("/complete", response_model=ChatResponse)
@limiter.limit("20/minute")
async def chat_complete(
    request: Request,
    body: ChatRequest = Body(...),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional),
):
    request_start = datetime.now(timezone.utc)
    user_id = current_user.get("id") if current_user else None
    warnings: List[str] = []

    # Retrieve context using enhanced index
    docs, trace = await retrieve_with_trace(body.message, top_k=body.top_k)

    if not docs:
        warnings.append("No relevant documents were found for this query.")
    elif trace.get("used_fallback"):
        warnings.append("Primary index returned low-confidence results; answer used the pgvector fallback path.")
    elif trace.get("fallback_attempted"):
        conf = trace.get("retrieval_confidence")
        conf_str = f"{conf:.2f}" if conf is not None else "unknown"
        warnings.append(f"Retrieval confidence was low ({conf_str}) and the pgvector fallback found no additional results.")

    # "Similar questions others are asking" — a real cosine-similarity
    # lookup against previously-logged queries, not a placeholder number.
    # Best-effort: an empty list here just means no data yet / not configured.
    similar_queries: List[Dict[str, Any]] = []
    try:
        from ..vector.pgvector_store import find_similar_queries

        similar_queries = await asyncio.to_thread(find_similar_queries, body.message, 5)
    except Exception as e:
        print(f"[WARN] Similar-queries lookup failed: {e}")

    # Try to use your LLM client if available
    content = ""
    model = "none (retrieval-only fallback)"
    usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    try:
        # Import the LLM client wrapper class
        from ..llm.llm_client import LLMClient
        from ..llm.prompt_engineering import get_prompt_for_query

        client = LLMClient()
        context_texts = _build_context_texts(docs)
        context_texts, context_truncated = _enforce_token_budget(context_texts)
        if context_truncated:
            warnings.append(
                f"Retrieved context exceeded the {MAX_CONTEXT_TOKENS}-token budget; the least-relevant sources were dropped before generation."
            )
        messages = get_prompt_for_query(body.message, context_texts)

        result = await client.complete_with_messages(messages)
        content = result["content"]

        # Reflect whichever backend actually ran (OpenAI or Gemini), not a guess
        model = getattr(client.backend, "model", model)

        # Get usage info if available
        usage = client.last_usage or usage

        if body.debug:
            print(f"LLM Success - Model: {model}, Content length: {len(content)}")

    except Exception as e:
        error_msg = f"LLM Error: {e}"
        print(error_msg)  # Debug logging

        if body.debug:
            content = f"{error_msg}\n\n"

        # Enhanced fallback response
        if docs:
            google_drive_docs = [d for d in docs if d.get("metadata", {}).get("source") == "google_drive"]
            local_docs = [d for d in docs if d.get("metadata", {}).get("source") != "google_drive"]

            fallback_parts = ["Here's what I found relevant to your query:"]

            if google_drive_docs:
                fallback_parts.append("\nFrom your Google Drive Excel files:")
                for d in google_drive_docs[:2]:
                    fallback_parts.append(f"- {d.get('text','')[:400]}")

            if local_docs:
                fallback_parts.append("\nFrom local documents:")
                for d in local_docs[:2]:
                    fallback_parts.append(f"- {d.get('text','')[:400]}")

            fallback_content = "\n".join(fallback_parts)
            content = content + fallback_content if body.debug else fallback_content
        else:
            fallback_content = (
                "I couldn't find relevant documents for that request. "
                "The enhanced index may need to be updated with your Google Drive files."
            )
            content = content + fallback_content if body.debug else fallback_content

    chat_id = str(uuid.uuid4())
    processing_time_ms = int((datetime.now(timezone.utc) - request_start).total_seconds() * 1000)

    resp = {
        "chat_id": chat_id,
        "content": content,
        "model": model,
        "sources": _render_sources(docs, limit=body.top_k),
        "created": datetime.now(timezone.utc).isoformat(),
        "warnings": warnings,
        "usage": usage,
        "trace": trace,
        "similar_queries": similar_queries,
    }

    # Best-effort audit logging (fact_query + bridge_query_citation) — never
    # blocks or fails the chat response if Supabase isn't configured/reachable.
    try:
        from ..vector.pgvector_store import log_query, upsert_query_embedding

        await asyncio.to_thread(
            log_query,
            query_id=chat_id,
            query_text=body.message,
            top_k=body.top_k,
            used_fallback=bool(trace.get("used_fallback")),
            retrieval_confidence=trace.get("retrieval_confidence"),
            processing_time_ms=processing_time_ms,
            citations=docs,
            user_id=user_id,
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            total_tokens=usage.get("total_tokens"),
        )
        # Stored after logging (not before) so this query only becomes
        # discoverable to *future* similar-queries lookups, never its own.
        await asyncio.to_thread(upsert_query_embedding, chat_id, body.message)
    except Exception as e:
        print(f"[WARN] Audit logging failed: {e}")

    return resp


# =========================
# Streaming (SSE)
# =========================

# ─────────────────────────────────────────────────────────────────────────
# [OPS:CHAT-019] _sse_event() — formats one Server-Sent Event frame
#
# WHAT: the SSE wire format is literally "event: <name>\ndata: <json>\n\n"
#       — two trailing newlines mark the end of a frame. This is the one
#       place that format is constructed, so [OPS:CHAT-020]'s generator
#       just calls this repeatedly with different event names/payloads.
# CONSUMED BY (frontend): page.tsx's hand-rolled SSE parser
#       [OPS:FE-CHAT] — splits on "\n\n" to find frame boundaries, then
#       "\n" to find the event:/data: lines within one frame.
# ─────────────────────────────────────────────────────────────────────────
def _sse_event(event: str, data: Dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


# ─────────────────────────────────────────────────────────────────────────
# [OPS:CHAT-020] POST /stream — the streaming chat endpoint
#
# WHAT: identical retrieval+generation pipeline to [OPS:CHAT-015]
#       chat_complete(), restructured as an async generator so each
#       piece of the answer can reach the client the moment it's
#       available, instead of the client waiting for the entire
#       response to finish generating.
#
# EVENT SEQUENCE (in the order they actually fire):
#   meta    → retrieval is done, before generation starts: chat_id,
#             sources, trace, warnings, similar_queries.
#   warning → optional, only if context had to be truncated mid-flow.
#   token   → one per chunk streamed back from the LLM (many of these).
#   error   → only if generation itself fails AFTER retrieval succeeded
#             (retrieval failures are already folded into "warnings" in
#             the meta event, not sent as a separate error).
#   done    → generation finished: chat_id, model, usage (estimated —
#             see the comment on prompt_tokens/completion_tokens below),
#             processing_time_ms.
#
# WHY usage IS ESTIMATED HERE (not exact, unlike a real API-reported
#       count): neither Gemini's nor OpenAI's streaming API reports
#       token usage consistently on every chunk — so this reuses the
#       same 4-chars/token heuristic as [OPS:CHAT-014]'s context budget,
#       applied to the actual prompt text and the actual generated
#       content, after the fact.
# API/CALL: Gemini generate_content_stream (via
#       [OPS:LLM-004] LLMClient.stream_with_messages()).
# RATE LIMIT: 20/minute — same limit as /complete, since it's the same
#       underlying cost (one retrieval + one generation call).
# request_start IS CAPTURED OUTSIDE event_generator() specifically so
#       processing_time_ms measures the whole request lifecycle,
#       matching how /complete measures it — not just the generator's
#       own runtime.
# ─────────────────────────────────────────────────────────────────────────
@router.post("/stream")
@limiter.limit("20/minute")
async def chat_stream(
    request: Request,
    body: ChatRequest = Body(...),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional),
):
    """
    Same retrieval + generation pipeline as /complete, but streams the
    answer as Server-Sent Events instead of waiting for the full
    completion. Event types:
      - meta: retrieval finished — chat_id, sources, trace, warnings
      - token: one incremental piece of the answer's text
      - warning: a non-fatal issue (e.g. context truncation) discovered mid-stream
      - error: generation failed; a retrieval-only summary is not sent here,
        the frontend should show the error and let the user retry
      - done: generation finished — usage + processing time

    Uses request_start captured before the async generator runs so
    processing_time_ms reflects the whole request, matching /complete.
    """
    request_start = datetime.now(timezone.utc)
    user_id = current_user.get("id") if current_user else None

    async def event_generator():
        warnings: List[str] = []
        docs, trace = await retrieve_with_trace(body.message, top_k=body.top_k)

        if not docs:
            warnings.append("No relevant documents were found for this query.")
        elif trace.get("used_fallback"):
            warnings.append("Primary index returned low-confidence results; answer used the pgvector fallback path.")
        elif trace.get("fallback_attempted"):
            conf = trace.get("retrieval_confidence")
            conf_str = f"{conf:.2f}" if conf is not None else "unknown"
            warnings.append(f"Retrieval confidence was low ({conf_str}) and the pgvector fallback found no additional results.")

        chat_id = str(uuid.uuid4())
        sources = _render_sources(docs, limit=body.top_k)

        similar_queries: List[Dict[str, Any]] = []
        try:
            from ..vector.pgvector_store import find_similar_queries

            similar_queries = await asyncio.to_thread(find_similar_queries, body.message, 5)
        except Exception as e:
            print(f"[WARN] Similar-queries lookup failed: {e}")

        yield _sse_event(
            "meta",
            {
                "chat_id": chat_id,
                "sources": sources,
                "trace": trace,
                "warnings": warnings,
                "similar_queries": similar_queries,
                "created": datetime.now(timezone.utc).isoformat(),
            },
        )

        content_parts: List[str] = []
        model = "none (retrieval-only fallback)"
        prompt_text = ""

        try:
            from ..llm.llm_client import LLMClient
            from ..llm.prompt_engineering import get_prompt_for_query

            client = LLMClient()
            context_texts = _build_context_texts(docs)
            context_texts, context_truncated = _enforce_token_budget(context_texts)
            if context_truncated:
                yield _sse_event(
                    "warning",
                    {
                        "message": (
                            f"Retrieved context exceeded the {MAX_CONTEXT_TOKENS}-token budget; "
                            "the least-relevant sources were dropped before generation."
                        )
                    },
                )
            messages = get_prompt_for_query(body.message, context_texts)
            prompt_text = "\n".join(m.get("content", "") for m in messages)
            model = getattr(client.backend, "model", model)

            async for chunk in client.stream_with_messages(messages):
                content_parts.append(chunk)
                yield _sse_event("token", {"content": chunk})

        except Exception as e:
            yield _sse_event("error", {"message": f"LLM Error: {e}"})

        content = "".join(content_parts)
        # No provider-agnostic streaming usage API to rely on (OpenAI/Gemini
        # report it differently, and not every chunk carries it) — reuse the
        # same 4-chars/token heuristic as the context token budget.
        prompt_tokens = _estimate_tokens(prompt_text) if prompt_text else 0
        completion_tokens = _estimate_tokens(content) if content else 0
        usage = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        }
        processing_time_ms = int((datetime.now(timezone.utc) - request_start).total_seconds() * 1000)

        yield _sse_event(
            "done",
            {
                "chat_id": chat_id,
                "model": model,
                "usage": usage,
                "processing_time_ms": processing_time_ms,
            },
        )

        try:
            from ..vector.pgvector_store import log_query, upsert_query_embedding

            await asyncio.to_thread(
                log_query,
                query_id=chat_id,
                query_text=body.message,
                top_k=body.top_k,
                used_fallback=bool(trace.get("used_fallback")),
                retrieval_confidence=trace.get("retrieval_confidence"),
                processing_time_ms=processing_time_ms,
                citations=docs,
                user_id=user_id,
                prompt_tokens=usage.get("prompt_tokens"),
                completion_tokens=usage.get("completion_tokens"),
                total_tokens=usage.get("total_tokens"),
            )
            await asyncio.to_thread(upsert_query_embedding, chat_id, body.message)
        except Exception as e:
            print(f"[WARN] Audit logging failed: {e}")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ─────────────────────────────────────────────────────────────────────────
# [OPS:CHAT-021] POST /feedback — thumbs up/down on a completed answer
#
# WHAT: query_id must match a chat_id from an earlier /complete or
#       /stream call. Writes straight to fact_query.user_rating via
#       [OPS:PVEC-008] set_feedback() — best-effort, "recorded": false
#       just means Supabase wasn't reachable, never a hard error, since
#       a missing audit write shouldn't visibly break the UI interaction
#       the user just performed.
# RATE LIMIT: 60/minute — much higher than chat endpoints, since a
#       feedback click is cheap (one DB update, no LLM/embedding calls).
# ─────────────────────────────────────────────────────────────────────────
@router.post("/feedback")
@limiter.limit("60/minute")
async def submit_feedback(
    request: Request,
    body: FeedbackRequest = Body(...),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional),
):
    """
    Thumbs up/down on a completed answer, keyed by the chat_id returned in
    the /complete or /stream response's `done`/root payload. Best-effort —
    if Supabase isn't configured this quietly no-ops rather than erroring,
    since a missing audit trail shouldn't block the UI interaction.
    """
    from ..vector.pgvector_store import set_feedback

    recorded = await asyncio.to_thread(set_feedback, body.query_id, body.rating)
    return {"recorded": recorded}


# ─────────────────────────────────────────────────────────────────────────
# [OPS:CHAT-022] GET /status — LLM + retrieval provider status
#
# WHAT: deliberately cheap and side-effect-free — no LLM calls, no
#       embedding calls; just checks which API key env vars are set and
#       whether pgvector_store.is_configured() [OPS:PVEC-001] returns
#       true. Meant to be safe to poll frequently (the frontend calls it
#       on every page load).
# ─────────────────────────────────────────────────────────────────────────
@router.get("/status")
def status():
    # Keep this super resilient (no external calls, other than a cheap local config check).
    llm_provider = "openai" if os.getenv("OPENAI_API_KEY") else ("gemini" if os.getenv("GEMINI_API_KEY") else "none")
    try:
        from ..vector.pgvector_store import is_configured as pgvector_is_configured
        pgvector_ready = pgvector_is_configured()
    except Exception:
        pgvector_ready = False

    return {
      "llm": {"ok": llm_provider != "none", "provider": llm_provider},
      "retrieval": {
          "ok": True,
          "primary": "enhanced_index (JSON, local)",
          "fallback": "supabase/pgvector" if pgvector_ready else "supabase/pgvector (not configured)",
          "fallback_ready": pgvector_ready,
      }
    }
# =========================
# Index Status Endpoints
# =========================

# ─────────────────────────────────────────────────────────────────────────
# [OPS:CHAT-023] GET /index/status — index file metadata, public, no auth
#
# WHAT: reads the index JSON file's size/mtime directly off disk — this
#       is what powers the frontend's "Synced X ago" badge (via
#       formatRelativeTime() on file_info.modified_epoch). Note the
#       index_metadata fields (version/total_documents/embedding_model)
#       are usually null in practice — the current index file format
#       doesn't carry those top-level keys, only "dim" and "items"; only
#       file_info (size, mtime) is reliably populated.
# ─────────────────────────────────────────────────────────────────────────
@router.get("/index/status")
def get_index_status():
    """
    Returns status of the enhanced index by checking a JSON file on disk.
    No external imports or helper functions required.
    """
    candidates = [
        Path("backend/app/features/rag_chatbot/vector/enhanced_index.json"),
        Path("app/features/rag_chatbot/vector/enhanced_index.json"),
    ]

    index_path = next((p for p in candidates if p.exists()), None)
    if not index_path:
        return {
            "status": "no_index",
            "message": "Enhanced index file not found",
            "suggestion": "Run gdrive_to_enhanced_index.py to create embeddings from Google Drive",
        }

    try:
        data = {}
        try:
            data = json.loads(index_path.read_text())
        except Exception:
            # file exists but not JSON → still return basic file info
            data = {}

        return {
            "status": "operational",
            "index_file": str(index_path),
            "index_metadata": {
                "version": data.get("version"),
                "total_documents": data.get("total_documents"),
                "embedding_model": data.get("embedding_model"),
                "embedding_dim": data.get("embedding_dim"),
                "created_at": data.get("created_at"),
                "source": data.get("source"),
            },
            "file_info": {
                "size_mb": round(index_path.stat().st_size / 1024 / 1024, 2),
                "modified_epoch": index_path.stat().st_mtime,
            },
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


# =========================
# Initialization (Simplified)
# =========================

# ─────────────────────────────────────────────────────────────────────────
# [OPS:CHAT-024] initialize_chat_system() — currently unused helper
#
# NUANCE: this function is not actually called anywhere in main.py's
#       startup sequence — main.py's lifespan does its own index-existence
#       check inline (with the Supabase rehydration logic layered on top,
#       see [OPS:MAIN-002]) rather than calling this. Left in place as a
#       simple standalone status check; worth knowing it's dead code if
#       asked "what does this do" — the honest answer is "nothing calls
#       it right now."
# ─────────────────────────────────────────────────────────────────────────
async def initialize_chat_system():
    """Initialize the simplified chat system."""
    try:
        # Just check if enhanced index exists
        vdir = _vector_dir()
        enhanced_index_path = vdir / "enhanced_index.json"

        if enhanced_index_path.exists():
            return {
                "status": "ready",
                "message": f"Chat system ready with enhanced index containing Google Drive data"
            }
        else:
            return {
                "status": "no_index",
                "message": "Enhanced index not found - chat system will use fallback",
                "suggestion": "Run gdrive_to_enhanced_index.py to create embeddings from Google Drive files"
            }

    except Exception as e:
        return {"status": "failed", "error": str(e)}
