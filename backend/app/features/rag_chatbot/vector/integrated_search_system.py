# backend/app/features/rag_chatbot/vector/integrated_search_system.py
from __future__ import annotations

import asyncio
import inspect
from typing import Any, Dict, List

# NOTE:
# Keep this module lightweight. Don't import heavy adapters/clients here.
# We only attempt to import real engines INSIDE methods.

class SimpleSearchInterface:
    """
    Minimal, robust wrapper around your real search engine.
    It tries to import your actual query engine at call time and adapts to
    different method names / signatures. Returns a simple list[dict] with
    'snippet' / 'score' / 'metadata'.
    """

    def __init__(self) -> None:
        self._engine = None  # real engine instance (lazy)

    async def _lazy_engine(self):
        """Import and create the real engine only when needed."""
        if self._engine is not None:
            return self._engine

        # Try common engine modules/classes
        engine_cls = None
        err = None
        try:
            # Your repo has search/query_engine.py (symlinked in vector/)
            from ..search.query_engine import QueryEngine  # type: ignore
            engine_cls = QueryEngine
        except Exception as e:
            err = e

        if engine_cls is None:
            # As a last resort, return a noop engine that yields []
            class _Noop:
                async def search(self, *args, **kwargs): return []
                async def retrieve(self, *args, **kwargs): return []
                async def query(self, *args, **kwargs): return []
            self._engine = _Noop()
            return self._engine

        try:
            self._engine = engine_cls()
        except Exception:
            # If it requires init args, try without / with defaults; otherwise fallback to noop
            try:
                self._engine = engine_cls  # in case it's a module-level function container
            except Exception:
                class _Noop:
                    async def search(self, *a, **k): return []
                    async def retrieve(self, *a, **k): return []
                    async def query(self, *a, **k): return []
                self._engine = _Noop()
        return self._engine

    def _simplify(self, raw: Any) -> List[Dict[str, Any]]:
        """
        Convert whatever the engine returns into a flat list of dicts.
        We favor 'snippet' for display; chat.py maps it to 'text'.
        """
        out: List[Dict[str, Any]] = []

        if raw is None:
            return out

        # Already a list
        if isinstance(raw, list):
            for r in raw:
                out.extend(self._simplify(r)) if isinstance(r, list) else out.append(self._one(r))
            return out

        # Dict, tuple, object
        out.append(self._one(raw))
        return out

    def _one(self, r: Any) -> Dict[str, Any]:
        if isinstance(r, dict):
            snippet = (
                r.get("snippet")
                or r.get("text")
                or r.get("content")
                or r.get("page_content")
                or ""
            )
            score = (
                r.get("score")
                or (r.get("scores") or {}).get("final_score")
                or r.get("similarity")
                or r.get("relevance")
                or 0.0
            )
            meta = r.get("metadata", {}) or {}
            # promote common fields
            for k in ("document_id", "file_name", "path", "source", "chunk_index", "id"):
                if k in r and k not in meta:
                    meta[k] = r[k]
            return {"snippet": snippet, "score": score, "metadata": meta}

        if isinstance(r, (tuple, list)):
            if len(r) == 2:
                doc, score = r
                if isinstance(doc, dict):
                    m = self._one(doc)
                    m["score"] = score
                    return m
                return {"snippet": str(doc), "score": score, "metadata": {}}
            if len(r) >= 3:
                text, score, meta = r[0], r[1], r[2]
                return {"snippet": str(text), "score": score, "metadata": meta if isinstance(meta, dict) else {}}

        # object-like
        snippet = (
            getattr(r, "snippet", None)
            or getattr(r, "text", None)
            or getattr(r, "content", None)
            or getattr(r, "page_content", None)
            or ""
        )
        score = getattr(r, "score", 0.0)
        meta = getattr(r, "metadata", {}) or {}
        return {"snippet": snippet, "score": score, "metadata": meta}

    async def _call_engine(self, method_name: str, query: str, top_k: int | None) -> List[Dict[str, Any]]:
        eng = await self._lazy_engine()
        if not hasattr(eng, method_name):
            return []

        method = getattr(eng, method_name)
        is_coro = asyncio.iscoroutinefunction(method)

        # Inspect signature and adapt arguments
        try:
            sig = inspect.signature(method)
            params = sig.parameters
        except Exception:
            params = {}

        try:
            if top_k is None:
                res = await method(query) if is_coro else method(query)
            else:
                if "top_k" in params:
                    res = await method(query, top_k=top_k) if is_coro else method(query, top_k=top_k)
                elif "k" in params:
                    res = await method(query, k=top_k) if is_coro else method(query, k=top_k)
                elif "limit" in params:
                    res = await method(query, limit=top_k) if is_coro else method(query, limit=top_k)
                elif "n" in params:
                    res = await method(query, n=top_k) if is_coro else method(query, n=top_k)
                else:
                    # try positional
                    try:
                        res = await method(query, top_k) if is_coro else method(query, top_k)
                    except TypeError:
                        res = await method(query) if is_coro else method(query)
        except TypeError:
            # final fallback
            res = await method(query) if is_coro else method(query)

        return self._simplify(res)

    async def search(self, query: str, top_k: int | None = None, **kwargs) -> List[Dict[str, Any]]:
        """
        Main entry. Tries retrieve/search/query on the real engine.
        Always returns a list of dicts: {"snippet", "score", "metadata"}.
        """
        for name in ("retrieve", "search", "query"):
            try:
                results = await self._call_engine(name, query, top_k)
                if results:
                    return results[: top_k or len(results)]
            except Exception:
                # try next method name
                continue
        return []

# Aliases so different import styles work
IntegratedSearchManager = SimpleSearchInterface
IntegratedSearchSystem = SimpleSearchInterface


# Compatibility alias for older imports
try:
    ComprehensiveSearchSystem
except NameError:
    # If the real class is IntegratedSearchSystem, alias it:
    try:
        ComprehensiveSearchSystem = IntegratedSearchSystem  # type: ignore
    except NameError:
        pass
