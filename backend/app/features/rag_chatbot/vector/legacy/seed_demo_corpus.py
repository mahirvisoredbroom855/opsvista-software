from __future__ import annotations
import argparse, asyncio, importlib, inspect, sys, time
from pathlib import Path
from typing import Any, Dict, List, Tuple

out_path = Path(os.getenv("RAG_INDEX_PATH", Path(__file__).parent / "enhanced_index.json"))
os.environ.setdefault("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
os.environ["USE_MOCK_EMBEDDINGS"] = "false"
# ... then build and save to out_path

SEARCH_MODULES = [
    "app.features.rag_chatbot.vector.integrated_search_system",
    "app.features.rag_chatbot.vector.simple_integrated_search",
    "app.features.rag_chatbot.vector.search_integration",
]

FACTORY_FUNCS = [
    "create_comprehensive_search_system",  # often async
    "create_simple_search_system",
    "get_production_search_manager",
]

CLASS_HINTS = [
    "ComprehensiveSearchSystem",
    "SimpleIntegratedSearchSystem",
    "IntegratedSearchManager",
]

INGEST_HINTS = ["ingest", "index", "upsert", "add", "insert", "bulk", "populate", "bootstrap", "load", "embed"]
SEARCH_HINTS = ["search", "semantic_search", "retrieve", "query", "similarity_search", "vector_search", "search_documents"]
NESTED_ATTRS = ["adapter", "vector_client", "client", "db", "index", "engine", "manager", "integration", "store", "pipeline"]

def _read_docs_from_path(p: Path) -> List[Dict[str, Any]]:
    docs: List[Dict[str, Any]] = []
    if p.is_dir():
        for ext in (".txt", ".md"):
            for fp in p.rglob(f"*{ext}"):
                text = fp.read_text(errors="ignore")
                if text.strip():
                    docs.append({"id": fp.stem, "text": text, "metadata": {"filename": fp.name, "path": str(fp)}})
    elif p.is_file():
        text = p.read_text(errors="ignore")
        if text.strip():
            docs.append({"id": p.stem, "text": text, "metadata": {"filename": p.name, "path": str(p)}})
    return docs

def _default_demo_docs() -> List[Dict[str, Any]]:
    return [
        {
            "id": "sop-onboarding",
            "text": (
                "Onboarding SOP (HR)\n"
                "All new employees must complete orientation within 3 business days of joining. "
                "They must submit required documents to HRIS and complete security training. "
                "Managers are responsible for equipment provisioning and a 30/60/90 plan."
            ),
            "metadata": {"category": "hr", "source": "seed_demo"}
        },
        {
            "id": "lc-policy",
            "text": (
                "Letter of Credit Policy (Finance)\n"
                "All LCs over 50,000 USD require dual approval from Finance Director and COO. "
                "Shipments without confirmed LC terms are not released. "
                "Discrepancies must be reported within 48 hours."
            ),
            "metadata": {"category": "lc", "source": "seed_demo"}
        },
    ]

async def _maybe_await(x):
    return await x if inspect.iscoroutine(x) else x

async def _get_system(verbose: bool = False) -> Tuple[Any | None, str | None, str | None]:
    for mname in SEARCH_MODULES:
        try:
            mod = importlib.import_module(mname)
        except Exception as e:
            if verbose: print(f"[WARN] import {mname} failed: {e}")
            continue

        # prefer factories
        for fname in FACTORY_FUNCS:
            if hasattr(mod, fname):
                try:
                    obj = getattr(mod, fname)()
                    inst = await _maybe_await(obj)
                    if verbose: print(f"[DEBUG] {mname}.{fname}() -> {type(inst).__name__}")
                    return inst, mname, f"{fname}()"
                except Exception as e:
                    if verbose: print(f"[WARN] {mname}.{fname}() failed: {e}")

        # classes fallback
        for cname in CLASS_HINTS:
            if hasattr(mod, cname):
                cls = getattr(mod, cname)
                try:
                    inst = cls()
                    if verbose: print(f"[DEBUG] {mname}.{cname}() -> {type(inst).__name__}")
                    return inst, mname, cname
                except Exception as e:
                    if verbose: print(f"[WARN] {mname}.{cname}() failed: {e}")

    return None, None, None

def _iter_targets(root: Any, max_depth: int = 2):
    seen = set()
    queue: List[Tuple[Any, str, int]] = [(root, "root", 0)]
    while queue:
        obj, path, depth = queue.pop(0)
        if id(obj) in seen:
            continue
        seen.add(id(obj))
        yield obj, path
        if depth >= max_depth:
            continue
        for name in NESTED_ATTRS:
            if hasattr(obj, name):
                try:
                    child = getattr(obj, name)
                except Exception:
                    continue
                queue.append((child, f"{path}.{name}", depth + 1))

def _find_method(target: Any, name_hints: List[str], param_shapes: List[List[str]], verbose: bool = False):
    import inspect as _inspect
    for attr in dir(target):
        if attr.startswith("_"):
            continue
        if not any(h in attr.lower() for h in name_hints):
            continue
        fn = getattr(target, attr)
        if not callable(fn):
            continue
        try:
            sig = _inspect.signature(fn)
            params = list(sig.parameters.keys())
        except Exception:
            params = []
        if verbose:
            print(f"[DEBUG] candidate {target.__class__.__name__}.{attr}({', '.join(params)})")
        for shape in param_shapes:
            if all(s in params for s in shape):
                return fn, attr, params
        if any(s in params for s in sum(param_shapes, [])):
            return fn, attr, params
    return None, None, None

async def _call_fn(fn, **kwargs):
    try:
        res = fn(**kwargs)
    except TypeError:
        res = fn()
    return await _maybe_await(res)

async def amain(path: str | None, top_k: int, verbose: bool):
    # 1) docs
    docs = _read_docs_from_path(Path(path)) if path else _default_demo_docs()
    if not docs:
        print("[ERR] No docs to ingest.")
        sys.exit(1)

    # 2) try your integrated system FIRST
    system_obj, module_name, how = await _get_system(verbose=verbose)
    if system_obj:
        print(f"[INFO] Using system from {module_name} via {how}: {system_obj.__class__.__name__}")

        # find ingest
        shapes = [["documents"], ["texts", "metadatas", "ids"], ["records"], ["items"], ["chunks"], ["entries"]]
        ingest_fn = ingest_params = ingest_target = None
        for obj, p in _iter_targets(system_obj):
            fn, name, params = _find_method(obj, INGEST_HINTS, shapes, verbose=verbose)
            if fn:
                ingest_fn, ingest_params, ingest_target = fn, params, obj
                print(f"[INFO] Found ingest: {obj.__class__.__name__}.{name}({', '.join(params or [])}) at {p}")
                break

        if ingest_fn:
            t0 = time.perf_counter()
            try:
                if "documents" in (ingest_params or []):
                    await _call_fn(ingest_fn, documents=docs)
                elif all(p in (ingest_params or []) for p in ["texts", "metadatas", "ids"]):
                    await _call_fn(
                        ingest_fn,
                        texts=[d["text"] for d in docs],
                        metadatas=[d.get("metadata", {}) for d in docs],
                        ids=[d.get("id") for d in docs],
                    )
                else:
                    # try both shapes
                    try:
                        await _call_fn(ingest_fn, documents=docs)
                    except Exception:
                        await _call_fn(
                            ingest_fn,
                            texts=[d["text"] for d in docs],
                            metadatas=[d.get("metadata", {}) for d in docs],
                            ids=[d.get("id") for d in docs],
                        )
            except Exception as e:
                print(f"[WARN] Integrated ingest failed: {e}")
            else:
                took = round((time.perf_counter() - t0) * 1000, 2)
                print(f"[OK] Ingested {len(docs)} docs via integrated system in {took} ms")
                return

        print("[WARN] No compatible ingest method found on integrated system. Falling back to persisted index.")

    # 3) FALLBACK: persisted in-memory index (works today)
    from app.features.rag_chatbot.vector.persisted_inmemory_search import PersistedInMemorySearch
    idx = PersistedInMemorySearch()  # honors RAG_INDEX_PATH if set
    idx.ingest_documents(docs)
    print("[OK] Ingested docs into persisted in-memory index.")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", help="Folder or a single .txt/.md file; default uses built-in demo docs")
    ap.add_argument("--top-k", type=int, default=3)
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()
    asyncio.run(amain(args.path, args.top_k, args.verbose))

if __name__ == "__main__":
    main()
