# backend/app/features/rag_chatbot/api/chat.py
from __future__ import annotations

import os
import json
import uuid
import asyncio
import inspect
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Query, Body
from pydantic import BaseModel

router = APIRouter(prefix="/api/rag/chat", tags=["RAG Chat"])

# =========================
# Request / Response Models
# =========================

class ChatRequest(BaseModel):
    message: str
    top_k: int = 4
    debug: bool = False

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
# Integrated retrieval (fallback only)
# =========================

async def _integrated_retrieve(q: str, top_k: int) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Fallback retrieval using integrated system."""
    # Try both export names from the integrated module
    IntegratedSearchSystem = None
    err1 = err2 = None
    try:
        from ..vector.integrated_search_system import IntegratedSearchManager as IntegratedSearchSystem
    except Exception as e:
        err1 = e
        try:
            from ..vector.integrated_search_system import SimpleSearchInterface as IntegratedSearchSystem
        except Exception as e2:
            err2 = e2

    if IntegratedSearchSystem is None:
        return [], {
            "impl": "failed",
            "method": "integrated_import",
            "error": f"{err1!r} | {err2!r}",
        }

    try:
        system = IntegratedSearchSystem()

        # Find a method: retrieve/search/query
        method = None
        for name in ("retrieve", "search", "query"):
            if hasattr(system, name):
                method = getattr(system, name)
                break
        if method is None:
            return [], {"impl": "failed", "method": "integrated", "error": "No retrieve/search/query method"}

        # Call with whatever signature it supports
        is_coro = asyncio.iscoroutinefunction(method)
        try:
            sig = inspect.signature(method)
            params = sig.parameters
        except Exception:
            params = {}

        try:
            if "top_k" in params:
                res = await method(q, top_k=top_k) if is_coro else method(q, top_k=top_k)
            elif "k" in params:
                res = await method(q, k=top_k) if is_coro else method(q, k=top_k)
            elif "limit" in params:
                res = await method(q, limit=top_k) if is_coro else method(q, limit=top_k)
            elif "n" in params:
                res = await method(q, n=top_k) if is_coro else method(q, n=top_k)
            else:
                # try positional (q, top_k) then just (q)
                try:
                    res = await method(q, top_k) if is_coro else method(q, top_k)
                except TypeError:
                    res = await method(q) if is_coro else method(q)
        except TypeError as e:
            return [], {"impl": "failed", "method": "integrated_call", "error": str(e)}

        docs = [_norm_one(r) for r in (res or [])]
        # Enforce size here if upstream doesn't accept k
        docs = docs[:top_k]
        return docs, {"impl": "integrated", "method": getattr(method, "__name__", "unknown"), "count": len(docs)}
    except Exception as e:
        return [], {"impl": "failed", "method": "integrated_call", "error": str(e)}


# =========================
# Main retrieve function - Enhanced Index First
# =========================

async def retrieve_with_trace(q: str, top_k: int = 4, force_fake: bool = False):
    """
    Simplified retrieve_with_trace that prioritizes enhanced index.
    
    Args:
        q: Query string
        top_k: Number of results to return
        force_fake: Force use of enhanced index (renamed from fake for clarity)
    """
    # Primary: Use enhanced index (contains your Google Drive embedded data)
    docs, trace = _enhanced_retrieve(q, top_k)
    
    # If enhanced index has results, use them
    if docs:
        return docs, trace
    
    # Fallback: Try integrated system only if enhanced index fails or has no results
    if not force_fake:
        fdocs, ftrace = await _integrated_retrieve(q, top_k)
        if fdocs:
            ftrace["fallback_from"] = trace
            return fdocs, ftrace
    
    # Return empty results with trace
    trace["warning"] = "No results found in enhanced index or integrated system"
    return docs, trace


# =========================
# Routes
# =========================

@router.get("/_retrieve", response_model=RetrieveResponse)
async def retrieve_endpoint(
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

def _build_prompt(user_msg: str, docs: List[Dict[str, Any]]) -> str:
    parts = [f"User message: {user_msg}", "", "Context documents:"]
    
    for i, d in enumerate(docs, 1):
        metadata = d.get("metadata", {})
        source_indicator = ""
        if metadata.get("source") == "google_drive":
            source_indicator = " [Google Drive]"
        
        parts.append(f"[{i}]{source_indicator} {d.get('text','')[:1200]}")
    
    parts.append("")
    parts.append("Answer the user briefly using the context if relevant. If information comes from Google Drive files, mention this source.")
    return "\n".join(parts)

@router.post("/complete", response_model=ChatResponse)
async def chat_complete(body: ChatRequest = Body(...)):
    # Retrieve context using enhanced index
    docs, trace = await retrieve_with_trace(body.message, top_k=body.top_k)

    # Try to use your LLM client if available
    content = ""
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    try:
        # Import the LLM client wrapper class
        from ..llm.llm_client import LLMClient
        
        client = LLMClient(model=model)
        prompt = _build_prompt(body.message, docs)
        
        # Call the async complete method
        content = await client.complete(prompt)
        
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

    resp = {
        "chat_id": str(uuid.uuid4()),
        "content": content,
        "model": model,
        "sources": _render_sources(docs, limit=body.top_k),
        "created": datetime.now(timezone.utc).isoformat(),
        "usage": usage,
        "trace": trace,
    }
    return resp


# =========================
# Index Status Endpoints
# =========================

@router.get("/index/status")
async def get_index_status():
    """Get enhanced index status."""
    try:
        index = _get_enhanced_index()
        stats = index.get_stats()
        
        # Check if index file exists and get metadata
        index_path = getattr(index, "index_path", None)
        if index_path and Path(index_path).exists():
            with open(index_path, 'r') as f:
                index_data = json.load(f)
            
            return {
                "status": "operational",
                "index_file": str(index_path),
                "stats": stats,
                "index_metadata": {
                    "version": index_data.get("version"),
                    "total_documents": index_data.get("total_documents"),
                    "embedding_model": index_data.get("embedding_model"),
                    "embedding_dim": index_data.get("embedding_dim"),
                    "created_at": index_data.get("created_at"),
                    "source": index_data.get("source")
                }
            }
        else:
            return {
                "status": "no_index",
                "message": "Enhanced index file not found",
                "suggestion": "Run gdrive_to_enhanced_index.py to create embeddings from Google Drive"
            }
            
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


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