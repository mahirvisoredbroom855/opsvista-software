# backend/app/features/rag_chatbot/api/chat.py
"""
This file handles every question asked in the OpsVista chat. When
someone types a question and hits Send, the code here (reachable at
/api/rag/chat/complete for a one-shot reply, or /api/rag/chat/stream
for the live "typing" version) finds the right snippets of company
documents to answer from — trying a fast built-in search first, and
only checking a slower backup search if the fast one isn't confident
— sends those snippets to the AI to write an answer, sends that answer
back to the browser (word by word, for the streaming version — a
technique called "Server-Sent Events," which just means the server
keeps pushing small updates over one open connection), and then saves
a record of what happened so the observability dashboard has data to
show later.
"""
#
# MODULE: [OPS:CHAT] — the core request path
#
# What it does: three stages, in order. RETRIEVAL — find the document
# chunks that answer the question (dual-path: fast local search first,
# Supabase backup search only if needed). GENERATION — send those
# chunks to the AI, get a written answer back. AUDIT — save a record
# of what happened to Supabase, without ever letting a failed save
# block the actual answer.
#
# Every tagged comment below (e.g. [OPS:CHAT-010]) is grep-able — the
# same tags are reused in docs/CODE_INDEX.md and README.md.
#
# In practice: this file runs every time someone types into the OpsVista
# chat box and hits Send.
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
# What it does: message is the raw question text. top_k is how many
# document chunks to fetch (default 4 — matches how many source cards
# show under the answer). debug, when true, shows the raw error text
# if something fails instead of a generic message. FastAPI checks this
# shape automatically before either endpoint below ever runs, so a
# malformed request never reaches the actual code.
#
# Called by: chat_complete(), chat_stream() read this on every request.
#
# In practice: this is what lands on the server the instant someone
# types a question and hits Send.
# ─────────────────────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str
    top_k: int = 4
    debug: bool = False

# ─────────────────────────────────────────────────────────────────────────
# [OPS:CHAT-002] FeedbackRequest — the body shape for POST /feedback
#
# What it does: query_id must be a chat_id an earlier /complete or
# /stream call already returned — you can't leave feedback on a
# question that was never asked. rating can only be "up" or "down";
# anything else is rejected automatically.
#
# Called by: submit_feedback(). Ends up written to fact_query.user_rating
# via set_feedback() in pgvector_store.py.
#
# In practice: fires when someone clicks the thumbs up/down icon under
# an answer.
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
# What it does: the single-JSON-reply shape, as opposed to /stream's
# events split across meta/done. trace carries the retrieval details
# the frontend's Trace Panel reads directly. similar_queries defaults
# to an empty list rather than being left out, so the frontend never
# has to guess whether the field is missing or genuinely empty.
#
# In practice: this is the exact JSON /complete hands back — the
# answer text, citations, and all.
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
# What it does: the fast local search and the Supabase backup search
# hand back results in different native shapes — one's a plain Python
# dict, the other's a database row. This function reshapes either one
# into the exact same {text, score, metadata} format, so nothing
# downstream has to know or care which search found it. Written
# defensively (checking several possible field names) because it has
# to tolerate whatever shape a search backend hands it.
#
# Called by: _enhanced_retrieve(), _pgvector_retrieve() — once per result.
#
# In practice: whether an answer's source came from the fast index or
# the Supabase backup, this makes both look identical afterward.
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
# [OPS:CHAT-006] _get_enhanced_index() — loads the primary search for
#                 this request
#
# What it does: picks which index JSON file to use, checks its
# embedding size to decide whether it holds real AI embeddings or
# cheap placeholder ones, and builds a fresh search object around it.
# Runs this fresh on every single request — nothing is cached between
# calls. Fine at today's corpus size (~117 chunks, well under a
# second); the first place to look if this ever needs to scale up.
#
# Called by: _enhanced_retrieve(), once per request.
#
# In practice: this trip runs fresh on every single question typed in
# the chat box — nothing is ever cached between requests.
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
# What it does: always runs first. Loads the local search index
# (_get_enhanced_index()), asks it to search — which makes one API
# call to Gemini to turn the question into an embedding, then compares
# it against every stored chunk in memory, no other network calls.
# Returns the results plus a small trace note. If the index file is
# missing or corrupt, this doesn't crash — it just reports back
# "found nothing" and lets the caller decide what to do next.
#
# Called by: retrieve_with_trace(), always first.
#
# In practice: this is what runs the instant a question arrives, before
# anything else happens.
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
# [OPS:CHAT-008] _pgvector_retrieve()
#
# What it does: this is the backup search. It only runs when the fast
# search didn't find good results. It takes the question, converts it
# to a list of numbers (an embedding), and asks the Supabase database
# to find the closest-matching document chunks using that number list.
# Runs on a separate thread (asyncio.to_thread) since the Supabase
# client library blocks while waiting on the network, and this keeps
# it from freezing every other in-flight request.
#
# If Supabase isn't set up, or the search fails for any reason, it just
# returns an empty list — it never crashes the request.
#
# Called by: retrieve_with_trace(), only when needed.
#
# In practice: fires when someone asks something the fast index isn't
# confident about — an obscure finance or maintenance question, say.
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
# What it does: decides whether a search result is actually good
# enough to use. RAG_QUALITY_THRESHOLD (0.5 by default) is the minimum
# score a result needs to be trusted. _retrieval_confidence() is just
# the single best score among the results — a rough estimate, not a
# calibrated probability. _source_diversity() checks how many
# different files the results came from; a low number isn't
# necessarily bad, it's just worth surfacing rather than hiding.
#
# Set the threshold too high and the backup search fires on almost
# every request, adding delay for no benefit. Too low and it stops
# meaning anything.
#
# Called by: retrieve_with_trace().
#
# In practice: 0.5 is the line that decides whether OpsVista trusts its
# first answer or quietly double-checks.
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
# [OPS:CHAT-010] retrieve_with_trace() — the dual-path retrieval
#                 entrypoint (the single most important function in
#                 this file)
#
# What it does: always tries the fast local search first. Falls back
# to the Supabase backup search when either (a) the fast search found
# nothing, or (b) it found something but the confidence score is below
# the threshold — a weak result is treated exactly the same as no
# result. If the backup search finds something, it entirely replaces
# the first attempt (never merged), and the trace records why. If the
# backup also comes up empty, the original weak result is kept anyway
# — something beats nothing.
#
# Returns: (docs, trace) — trace is exactly what the frontend's Trace
# Panel displays.
#
# Called by: retrieve_endpoint() (the debug route), chat_complete(),
# chat_stream() — every entry point into retrieval goes through this
# one function.
#
# In practice: every single question typed into OpsVista passes through
# this one function first.
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
# What it does: exposes retrieve_with_trace() directly over HTTP, so
# you can see exactly what got retrieved for a question without paying
# for an AI call. use_fake=true skips the backup search entirely, so
# you can inspect the fast search alone. Limited to 30 requests/minute.
#
# In practice: use this to see exactly what got retrieved for a
# question, without waiting on an AI reply.
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
# What it does: trims the result list down to `limit` sources, and
# appends "(Google Drive)" to the label when a source really came from
# Drive. Purely presentational — distinct from _build_context_texts()
# below, which reshapes the same docs for the AI prompt instead.
#
# Consumed by (frontend): sources[] in the "meta" SSE event and
# ChatResponse.sources — rendered by SourceCard/SourcesToggle in page.tsx.
#
# In practice: this builds the little citation cards you see under
# every chat answer.
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
# What it does: caps how much retrieved text gets sent to the AI in
# one request (~6000 tokens by default — small word-pieces, not whole
# words). Chunks already arrive sorted best-to-worst, so it keeps
# adding chunks in that order until the budget runs out, dropping the
# least-relevant ones first. "4 characters per token" is a rough,
# deliberately-imprecise estimate — not a real tokenizer — since a
# precise one for OpenAI would be wrong for Gemini, and this app
# supports both. If a single chunk alone is bigger than the whole
# budget, it gets trimmed down to fit rather than dropped entirely.
#
# Called by: chat_complete(), chat_stream(), right before the prompt
# gets built.
#
# In practice: kicks in when a broad question like "summarize Q3
# finance" pulls back more source text than the AI can read in one go.
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
# [OPS:CHAT-015] POST /complete — the non-streaming chat endpoint
#                 (the original endpoint; /stream below is the newer
#                 SSE upgrade with the same underlying pipeline)
#
# What it does, in order: retrieve documents (retrieve_with_trace()) →
# note anything unusual as a warning (empty results? backup search
# used?) → separately check "has anyone asked something like this
# before?" as a bonus, never letting that block the answer if it fails
# → call the AI to write an answer — if that fails, fall back to
# showing the raw retrieved text instead of nothing → assemble the
# final response → only after the response is ready, quietly log the
# question to Supabase (writing the log entry before the "similar
# queries" fingerprint, so this exact question can never match itself
# later). No login required — an anonymous request still gets an answer.
#
# In practice: this is what runs if something outside the chat UI (a
# script, /docs) asks a question and just wants one plain JSON reply.
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
# What it does: the SSE wire format is "event: <name>\ndata: <json>\n\n"
# — two trailing newlines mark where one message ends. This is the
# only place that format gets built; chat_stream()'s generator just
# calls it repeatedly with different event names and payloads.
#
# Consumed by (frontend): page.tsx's SSE parser — splits on "\n\n" to
# find message boundaries, then "\n" for the event:/data: lines.
#
# In practice: every flickering word you see typed live in the OpsVista
# chat window passed through this line first.
# ─────────────────────────────────────────────────────────────────────────
def _sse_event(event: str, data: Dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


# ─────────────────────────────────────────────────────────────────────────
# [OPS:CHAT-020] POST /stream — the streaming chat endpoint
#
# What it does: identical retrieval + generation pipeline to
# chat_complete(), restructured as an async generator so each piece of
# the answer reaches the browser the moment it exists, instead of the
# client waiting for the whole thing to finish.
#
# Event order: meta (retrieval done, before generation starts: chat_id,
# sources, trace, warnings, similar_queries) → warning (only if context
# had to be trimmed) → token (one per chunk streamed from the AI — this
# is what makes the answer look like it's typing itself) → error (only
# if generation fails after retrieval succeeded) → done (chat_id,
# model, an estimated usage count, processing time).
#
# Usage is estimated, not exact, because neither AI provider reports
# token counts reliably mid-stream — this reuses the same 4-char/token
# estimate as the context budget. request_start is captured before the
# generator runs, so processing_time_ms measures the whole request.
#
# In practice: this is the actual function that runs when you hit Send
# in the OpsVista chat window.
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
# What it does: query_id must match a chat_id from an earlier
# /complete or /stream call. Writes straight to
# fact_query.user_rating. Best-effort — if the write fails, it just
# returns "recorded: false" instead of an error, since a missing audit
# write shouldn't visibly break the button the user just clicked.
# Allowed far more often than chat itself (60/minute vs 20/minute)
# since a feedback click is cheap — one database update, no AI call.
#
# In practice: fires the moment someone clicks a thumbs-up/down icon on
# a past answer.
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
# What it does: doesn't call the AI or the database at all — just
# checks which API-key environment variables are set, and whether
# Supabase is configured. Costs nothing, so it's safe for the frontend
# to check on every single page load.
#
# In practice: this is the tiny "LLM Online" note at the top of the
# chat page.
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
# What it does: reads the index file's size and last-changed time
# straight off disk, live, on every call — this is what powers the
# frontend's "Synced X ago" badge. A few of the reported fields
# (version, total_documents, embedding_model) are usually empty in
# practice, since the current index file format doesn't carry those
# details — only size and timestamp are reliably real.
#
# In practice: this is what powers the "Synced 3 hours ago" badge in
# the chat header.
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
# What it does: checks if the index file exists and returns a status
# dict — but nothing in the app actually calls this function.
# main.py's boot-time lifespan check does its own, separate version of
# this check (with Supabase self-healing logic added on top), and
# never calls this one. Left in place as dead code.
#
# In practice: if you go searching for what calls this, you won't find
# anything — it's unused.
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
