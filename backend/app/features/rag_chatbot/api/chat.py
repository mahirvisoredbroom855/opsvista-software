# backend/app/features/rag_chatbot/api/chat.py
#
# ═══════════════════════════════════════════════════════════════════════════
# MODULE: [OPS:CHAT] — the core request path
#
# Think of this file as a restaurant's kitchen on the night a customer's
# order comes in. Someone (the frontend) hands a slip of paper through the
# window with a question written on it. This file is everything that
# happens between that slip landing on the counter and a finished plate
# going back out: someone runs to the pantry to grab the right ingredients
# (RETRIEVAL — go find the document snippets that actually answer this),
# the chef turns those ingredients into a dish (GENERATION — hand them to
# the AI model and get a written answer back), and afterwards someone
# jots the order down in the restaurant's logbook for the manager to
# review later (AUDIT — write it to Supabase, but never let a broken pen
# stop the food from going out — logging failures never block an answer).
#
# Every tagged comment below (e.g. [OPS:CHAT-010]) is a labelled station
# in that kitchen — grep for the tag and you land exactly there. The same
# tags are reused in docs/CODE_INDEX.md and in README.md's architecture
# diagrams, so a tag means the same station no matter where you see it.
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
# [OPS:CHAT-001] ChatRequest — the order form the customer fills out
#
# This is the paper slip the frontend hands over: message is the actual
# question, written as-is with no cleanup expected. top_k is "how many
# ingredients to fetch" — 4 by default, which is exactly how many source
# cards show up under the answer, so turning this number up or down
# directly changes how many citations the user sees. debug is a chef's
# note that says "if this order goes wrong, show me the mess in the
# kitchen instead of just apologizing to the customer" — with it on, a
# failed AI call shows the raw error text instead of a generic message.
#
# Nobody in this file has to check that the slip was filled in correctly
# — FastAPI/Pydantic reads the shape above and rejects a bad order before
# it ever reaches the kitchen. The two places that receive this filled-in
# slip are [OPS:CHAT-015] chat_complete() and [OPS:CHAT-020] chat_stream().
# ─────────────────────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str
    top_k: int = 4
    debug: bool = False

# ─────────────────────────────────────────────────────────────────────────
# [OPS:CHAT-002] FeedbackRequest — a customer's comment card, referencing
#                 a specific past order
#
# This is a comment card the diner can only fill out if they can quote
# their receipt number — query_id has to be a chat_id the kitchen already
# handed them from an earlier order, so there's no way to leave feedback
# on a meal that was never actually served. rating can only be "up" or
# "down," nothing else — the Literal type is a printed comment card with
# only two boxes on it, so there's no way to write in a third option by
# mistake. [OPS:CHAT-021] submit_feedback() is the only place that reads
# this card, and it ends up as one written note (fact_query.user_rating)
# via [OPS:PVEC-008] set_feedback().
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
# [OPS:CHAT-004] ChatResponse — the finished plate, served all at once
#
# Where /stream hands the customer their meal course by course (an
# appetizer of sources, then the main course typed out bite by bite,
# then a dessert of usage stats), /complete just brings out the entire
# tray in one trip once everything is ready — same ingredients, same
# meal, different serving style. trace is the waiter's explanation of
# which kitchen station actually cooked this (see [OPS:CHAT-010]) — it's
# what the frontend's collapsible "Trace Panel" reads directly.
# similar_queries defaults to an empty list rather than being left off
# the tray entirely, so the frontend never has to guess "did the kitchen
# forget this, or genuinely have nothing to say" — an empty list always
# means the second one.
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
# [OPS:CHAT-005] _norm_one() — a universal power adapter for travel plugs
#
# Picture landing in a country where the wall socket doesn't match your
# charger — you need an adapter so your phone doesn't care which country
# it's in. That's this function. The fast in-memory search
# ([OPS:IDX-005] search()) and the Postgres backup search
# ([OPS:PVEC-004] pgvector_search()) hand back their results shaped
# completely differently — one's a plain Python dict, the other's a row
# straight out of a database query. This function plugs into either one
# and always outputs the same three prongs: {text, score, metadata}.
# Everything after this point in the file never has to ask "wait, which
# search found this?" — it just always gets the same shape.
#
# It's written defensively (checking for "score" or "similarity" or
# "relevance," "text" or "snippet" or "content") because it was built to
# survive whatever a search backend happened to hand it, even backends
# from earlier versions of this project that no longer exist. Called once
# per result, from both [OPS:CHAT-007] _enhanced_retrieve() and
# [OPS:CHAT-008] _pgvector_retrieve().
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
# [OPS:CHAT-006] _get_enhanced_index() — unlocking the pantry, fresh, every
#                 single time someone orders
#
# Before the kitchen can cook, someone has to go open the pantry and
# check what's actually on the shelf — this function is that trip. It
# figures out which pantry (which index JSON file) to open, peeks inside
# to see what kind of ingredients are stored there (the embedding
# dimension tells it whether these are "real" AI-generated ingredients
# or cheap placeholder ones — USE_MOCK_EMBEDDINGS), and hands back a
# fresh search tool built around whatever it found ([OPS:IDX-003]
# PersistedInMemorySearch).
#
# It makes this trip to the pantry on *every single question asked* —
# it never remembers what it saw last time. At today's corpus size
# (about 117 chunks) that trip takes a fraction of a second, so it's a
# non-issue, but if this system ever grew to hold a huge library of
# documents, this is the first place to look if things start feeling
# slow. Called once per request, from [OPS:CHAT-007] _enhanced_retrieve().
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
# [OPS:CHAT-007] _enhanced_retrieve() — sending the fastest runner to the
#                 nearest pantry first
#
# This is always the first person sent to go find ingredients — nobody
# calls an outside supplier before checking what's already on-site. It
# opens the pantry ([OPS:CHAT-006]) and asks it to search
# ([OPS:IDX-005] PersistedInMemorySearch.search()), which itself makes
# exactly one phone call out to Gemini (to turn the question into a
# numeric fingerprint) and then does all the actual comparing locally,
# in memory — nothing else leaves the building.
#
# Comes back with two things: the ingredients it found (docs — each one
# shaped {text, score, metadata}), and a little note about how the trip
# went (trace — this note is what eventually becomes the "trace" panel
# in [OPS:CHAT-010]). If the pantry itself turns out to be locked,
# empty, or the shelf labels are unreadable (the index file is
# missing/corrupt), this function doesn't panic the whole kitchen — it
# just reports back "found nothing" and lets the next step decide what
# to do. Always the first thing [OPS:CHAT-010] retrieve_with_trace() tries.
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
# [OPS:CHAT-008] _pgvector_retrieve() — calling the outside supplier,
#                 because the pantry didn't have enough
#
# This is the phone call to the second, off-site warehouse (Supabase's
# Postgres database) — placed only when the nearby pantry came back
# empty-handed or unconvincing. It calls [OPS:PVEC-004] pgvector_search(),
# which re-asks Gemini to fingerprint the question (a fresh phone call,
# not reusing the first one) and then asks the warehouse's own search
# tool (match_chunks(), a function living inside the database itself)
# to find matches there.
#
# This call is placed on a separate line (asyncio.to_thread) so that
# waiting for the warehouse to pick up the phone doesn't freeze every
# other customer's order in the kitchen at the same time — Supabase's
# client library doesn't know how to "wait politely," so it gets put on
# its own thread instead. And if the warehouse's phone just rings and
# rings (Supabase not configured, or the call fails), this function
# doesn't crash the kitchen — it just shrugs and reports back nothing.
# Only ever called by [OPS:CHAT-010] retrieve_with_trace(), and only
# when the first pantry trip wasn't good enough.
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
# [OPS:CHAT-009] Quality-gate helpers — the taste-tester before a dish
#                 leaves the kitchen
#
# A dish can come out of the pantry search and still not be good enough
# to serve — these three little pieces are the taste-test that decides
# that. RAG_QUALITY_THRESHOLD (0.5, unless someone turns the dial via an
# env var) is the minimum "this actually tastes right" score — anything
# below it gets sent back even though something technically came out of
# the kitchen. _retrieval_confidence() is just "how good was the single
# best thing we found" — a rough gut-check, not a scientific measurement,
# worth being honest about if someone asks whether it's a real
# probability (it isn't). _source_diversity() answers a different
# question: "did this meal come from one single dish, or from several
# different ones" — a low number isn't necessarily bad (sometimes one
# document really is the whole answer), it's just something worth
# mentioning out loud rather than hiding.
#
# Turn the taste-test threshold up too high and the kitchen starts
# calling the outside supplier on almost every order, adding delay for
# no real benefit. Turn it down too low and the taste-test stops meaning
# anything — bad dishes go out without a second opinion. Used entirely
# by [OPS:CHAT-010] retrieve_with_trace().
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
# [OPS:CHAT-010] retrieve_with_trace() — the head chef who decides
#                 whether the first dish is good enough to serve, or
#                 whether the outside supplier needs to be called
#                 (the single most important function in this whole file)
#
# Every single order starts the same way: send the fastest runner to the
# nearby pantry first, no exceptions ([OPS:CHAT-007]). Then the head
# chef tastes what came back and makes exactly one call: is this good
# enough to serve? Only two things would make the answer "no" —
# (a) the runner came back completely empty-handed, or (b) they brought
# something back, but the taste-test score is below the "good enough"
# line ([OPS:CHAT-009]). A weak, mediocre result is treated exactly the
# same as no result at all — there's no partial credit.
#
# If "no," the chef picks up the phone and calls the outside supplier
# ([OPS:CHAT-008]). If the supplier actually delivers something, that
# entirely REPLACES the first attempt — the two never get mixed
# together on one plate — and the ticket gets a note explaining exactly
# why the second call was made. If even the supplier comes up empty, the
# chef shrugs and serves the original weak dish anyway, because a
# mediocre answer beats an empty plate, and makes a note that both
# attempts happened.
#
# Whatever comes back — the dish itself, plus the ticket explaining how
# it was made — is exactly what the frontend's "Trace Panel" reads and
# displays to the customer. Every single door into this restaurant that
# needs food (the debug endpoint, /complete, /stream) walks through this
# one chef and no other — which means the "is this good enough" rule
# only ever has to be written correctly in one place.
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
# [OPS:CHAT-011] GET /_retrieve — the kitchen's back door, for a health
#                 inspector who just wants to see the ingredients, not
#                 eat the meal
#
# This lets someone stand right next to [OPS:CHAT-010]'s head chef and
# watch the exact same pantry-then-supplier decision happen, without
# ordering a finished meal — no AI call, no cost, just "show me what you
# found and why." The use_fake switch is a note pinned to the ticket
# that says "don't bother calling the outside supplier even if you'd
# normally want to" — useful when you specifically want to see what the
# nearby pantry alone has, with nothing else muddying the picture.
# Limited to 30 requests/minute so nobody can hammer it accidentally
# (see [OPS:RATE-001]).
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
# [OPS:CHAT-012] _render_sources() — writing the ingredient labels the
#                 customer actually sees on the receipt
#
# Same ingredients as the kitchen used, but relabelled for the dining
# room — this is purely about presentation, distinct from the function
# right below it which repackages the very same ingredients for the
# chef's own recipe card instead. It trims the list down to however many
# sources should show (limit), and tacks "(Google Drive)" onto the label
# when a source really did come from Drive, so the diner knows where
# their food came from. This is exactly what shows up as the citation
# cards under an answer in the chat UI — read directly by SourceCard /
# SourcesToggle in page.tsx.
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
# [OPS:CHAT-014] Token budget — packing a suitcase that has a weight limit
#
# There's a limit to how much luggage the AI can carry onto the plane
# (roughly 6000 "tokens" — small word-pieces, not whole words — unless
# someone changes the dial). The ingredients already arrive sorted
# best-to-worst, so the packing strategy is simple: keep throwing things
# in the suitcase in that order until it won't zip shut, then stop —
# which means whatever gets left behind is always the least important
# stuff, never the best.
#
# "4 characters per token" is a rough, deliberately-imprecise ruler — not
# a real tokenizer — because a precisely-correct ruler for one AI
# provider (OpenAI's tiktoken) would be precisely wrong for the other
# one this app also supports (Gemini). Close enough beats exactly wrong.
# One special case: if a single item is bigger than the whole suitcase
# by itself, it doesn't get left behind entirely — it gets trimmed down
# to fit, because a partial souvenir beats no souvenir at all. Used by
# both /complete and /stream, right before the prompt gets built.
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
# [OPS:CHAT-015] POST /complete — the sit-down meal, served all at once
#                 once it's completely ready (the original way this
#                 kitchen served food; /stream, below, is the newer
#                 "food comes out as it's cooked" version of the exact
#                 same recipe)
#
# The whole order, start to finish: go find ingredients
# ([OPS:CHAT-010]) → jot down anything unusual on the ticket for the
# customer to see (empty pantry? had to call the supplier? that's a
# "warning") → separately, quietly check "has anyone ordered something
# like this before?" as a bonus, never letting that check hold up the
# meal if it fails → hand the ingredients to the chef to actually cook
# (the AI call) — if the chef can't cook for any reason, the raw
# ingredients get served plain instead of an empty plate → plate
# everything up into the finished response → and only after the
# customer already has their food, quietly write the order down in the
# restaurant's logbook (writing the log entry before the "have I seen
# this order before" fingerprint, specifically so this exact order can
# never show up as its own "similar order" later). No login required to
# eat here — an anonymous diner still gets served, their receipt just
# has no name on it.
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
# [OPS:CHAT-019] _sse_event() — folding one note and sliding it under the
#                 door, in a format the person on the other side already
#                 knows how to unfold
#
# Two people passing notes under a door need to agree in advance on how
# to tell where one note ends and the next begins — here that agreement
# is "every note ends with exactly two blank lines." This one small
# function is the only place in the whole backend that folds a note this
# way; [OPS:CHAT-020]'s generator just keeps calling it with different
# messages. On the other side of the door, page.tsx's parser is doing
# the exact reverse — unfolding notes by looking for those same two
# blank lines.
# ─────────────────────────────────────────────────────────────────────────
def _sse_event(event: str, data: Dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


# ─────────────────────────────────────────────────────────────────────────
# [OPS:CHAT-020] POST /stream — the exact same meal as /complete, but
#                 brought to the table course by course instead of all
#                 at once
#
# Same kitchen, same recipe, same ingredients as [OPS:CHAT-015] — the
# only thing that changes is how it's served. Instead of waiting in the
# kitchen until the entire tray is ready, each piece goes out to the
# table the moment it exists. In order: an "appetizer" note arrives
# first, before the chef has even started cooking — it tells the
# customer which ingredients are being used, so they know what's coming.
# Then, if the ingredients had to be trimmed to fit the suitcase
# ([OPS:CHAT-014]), a quick "heads up" note. Then the main course comes
# out one small bite at a time, as the chef finishes each piece — this
# is the part that makes the answer look like it's "typing itself" on
# screen. If the chef burns the dish partway through, one apology note
# explains what went wrong. And finally, a closing note: which chef
# cooked it, roughly how much was eaten (an estimate, since neither AI
# provider reliably reports an exact count mid-stream — reusing the same
# rough 4-characters-per-token ruler from [OPS:CHAT-014]), and how long
# the whole meal took, timed from the moment the order was placed, not
# just from when cooking started.
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
# [OPS:CHAT-021] POST /feedback — the comment card getting dropped in the
#                 box by the door on the way out
#
# The card has to name a real receipt (query_id must match a chat_id
# from an earlier meal) — no anonymous complaints about a meal that was
# never served. Writing it down is a quick, cheap, low-stakes action
# ([OPS:PVEC-008] set_feedback() — just one line in a logbook), so if the
# logbook happens to be locked at that exact moment, the diner still
# walks out feeling fine — they get a quiet "recorded: false" instead of
# the restaurant making a scene about it. Allowed far more often than
# ordering food (60/minute vs 20/minute) because dropping a card in a
# box costs the kitchen nothing.
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
# [OPS:CHAT-022] GET /status — reading the "OPEN" sign in the window,
#                 not actually walking inside
#
# This doesn't call the chef or the supplier at all — it just glances at
# which keys are hanging by the door (which API-key env vars are set)
# and whether the warehouse's phone line is even plugged in
# ([OPS:PVEC-001] is_configured()). Costs nothing, so it's safe for the
# frontend to check this every single time someone loads the page.
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
# [OPS:CHAT-023] GET /index/status — checking the "best before" stamp on
#                 the pantry itself
#
# This one does walk over and physically look at the pantry file's size
# and last-changed timestamp, live, every time it's called — that's what
# lets the frontend's "Synced X ago" badge tell the truth right now, not
# just at boot time. Fair warning: a few of the fields this reports
# (version, total_documents, embedding_model) are usually empty in
# practice, because the pantry's actual label format doesn't carry those
# details today — only the size and timestamp are reliably real.
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
# [OPS:CHAT-024] initialize_chat_system() — a spare key nobody uses
#
# Somebody cut this key and hung it on the wall, but the actual front
# door (main.py's boot-time lifespan check) uses a different, newer
# lock now — one with the Supabase self-healing logic built in
# ([OPS:MAIN-002]). This key still turns, technically, but nothing in
# the building ever reaches for it. Worth being upfront about if asked
# "what does this do" — the honest answer is "nothing calls it, it's
# leftover."
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
