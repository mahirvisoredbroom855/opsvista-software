# backend/app/features/rag_chatbot/api/chat.py
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

class ChatRequest(BaseModel):
    message: str
    top_k: int = 4
    debug: bool = False

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

def _sse_event(event: str, data: Dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


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
    

