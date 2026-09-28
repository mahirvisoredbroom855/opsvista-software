# ═══════════════════════════════════════════════════════════════════════
# MODULE: [OPS:IDX] — the PRIMARY retrieval path (in-memory JSON index)
#
# This is what [OPS:CHAT-007] _enhanced_retrieve() searches first, before
# any pgvector fallback [OPS:PVEC] is even considered. Two responsibilities
# live in this one file: (1) embed_texts() — the single shared embedding
# entrypoint reused by the primary index, the pgvector dual-write, and the
# pgvector query path, so all three stay in the same vector space; and
# (2) PersistedInMemorySearch — a brute-force cosine-similarity scan over
# a JSON file loaded fully into memory (no ANN index, no database — see
# [OPS:CHAT-006]'s note on why this is fine at current corpus size).
# ═══════════════════════════════════════════════════════════════════════
from __future__ import annotations
import json, math, os, hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional
import os
import json
from pathlib import Path
from typing import Any, Dict, List, Optional


try:
    import numpy as np
except Exception:
    np = None  # we'll do pure-Python cosine if numpy isn't available

# Mock embedding model - no OpenAI required
_EMBED_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
_MOCK_DIM = 384  # Standard embedding dimension

# ─────────────────────────────────────────────────────────────────────────
# [OPS:IDX-001] _cosine() / _hash_to_vector() — the math primitive and the
#                deterministic mock-embedding fallback
#
# WHAT: _cosine() is the same similarity function pgvector's `<=>` operator
#       computes server-side [OPS:PVEC-004] — kept identical in meaning
#       (via `1 - distance` on the Postgres side) so scores from the two
#       retrieval paths are comparable to a human even though they're
#       computed on different machines. _hash_to_vector() produces a
#       deterministic (same text -> same vector, every run) but
#       semantically meaningless embedding via repeated MD5 hashing +
#       normalization — used only when no real API key is configured, so
#       the whole pipeline (ingest, search, score) is exercisable without
#       any API cost during local dev.
# CALLED BY: [OPS:IDX-005] PersistedInMemorySearch.search() (_cosine, every
#       query); [OPS:IDX-002] embed_texts() (_hash_to_vector, mock path only).
# ─────────────────────────────────────────────────────────────────────────
def _cosine(a: List[float], b: List[float]) -> float:
    if np is not None:
        aa = np.asarray(a); bb = np.asarray(b)
        denom = (np.linalg.norm(aa) * np.linalg.norm(bb)) or 1e-12
        return float(np.dot(aa, bb) / denom)
    # pure python
    dot = sum(x*y for x, y in zip(a, b))
    na = math.sqrt(sum(x*x for x in a)) or 1e-12
    nb = math.sqrt(sum(y*y for y in b)) or 1e-12
    return dot / (na * nb)

def _hash_to_vector(text: str, dim: int = _MOCK_DIM) -> List[float]:
    """
    Create a deterministic mock embedding from text using hash functions.
    This provides consistent vectors for the same text without requiring OpenAI.
    """
    # Create multiple hash seeds for different dimensions
    vector = []
    for i in range(dim):
        # Use different seeds to get varied hash values
        seed_text = f"{text}_{i}"
        hash_val = int(hashlib.md5(seed_text.encode()).hexdigest()[:8], 16)
        # Normalize to [-1, 1] range
        normalized = (hash_val / (2**32 - 1)) * 2 - 1
        vector.append(normalized)
    
    # Normalize the vector to unit length for proper cosine similarity
    length = math.sqrt(sum(x*x for x in vector))
    if length > 0:
        vector = [x / length for x in vector]
    
    return vector


def _embed_many_openai_impl(texts: List[str]) -> List[List[float]]:
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    embeddings = []
    batch_size = 100  # Adjust based on your rate limits

    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        resp = client.embeddings.create(model=_EMBED_MODEL, input=batch)
        embeddings.extend([d.embedding for d in resp.data])

        # Brief pause between batches to respect rate limits
        if i + batch_size < len(texts):
            import time
            time.sleep(0.1)

    print(f"[INFO] Generated {len(embeddings)} OpenAI embeddings")
    return embeddings


def _embed_many_gemini_impl(texts: List[str]) -> List[List[float]]:
    from google import genai
    from google.genai import types

    import time

    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    model = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")
    # gemini-embedding-001 defaults to 3072 dims, which exceeds pgvector's
    # 2000-dim cap for ivfflat/hnsw indexes. Request a smaller output
    # dimension (Matryoshka representation learning) so the same vectors are
    # usable for both the JSON index and an indexed pgvector fallback.
    output_dim = int(os.getenv("GEMINI_EMBEDDING_DIM", "1536"))

    # Conservative batch size + retry/backoff on 429s: the free tier has
    # fairly tight rate limits (requests/minute), and a bare 429 should
    # slow down and retry rather than silently abandon the whole batch.
    embeddings: List[List[float]] = []
    batch_size = int(os.getenv("GEMINI_EMBED_BATCH_SIZE", "10"))
    inter_batch_delay = float(os.getenv("GEMINI_EMBED_DELAY_SECONDS", "2.0"))
    max_retries = 5

    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        for attempt in range(max_retries):
            try:
                resp = client.models.embed_content(
                    model=model,
                    contents=batch,
                    config=types.EmbedContentConfig(output_dimensionality=output_dim),
                )
                embeddings.extend([e.values for e in resp.embeddings])
                break
            except Exception as e:
                is_rate_limit = "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e)
                if is_rate_limit and attempt < max_retries - 1:
                    backoff = inter_batch_delay * (2 ** attempt)
                    print(f"[WARN] Gemini rate limited (attempt {attempt + 1}/{max_retries}), retrying in {backoff:.0f}s...")
                    time.sleep(backoff)
                    continue
                raise

        if i + batch_size < len(texts):
            time.sleep(inter_batch_delay)

    print(f"[INFO] Generated {len(embeddings)} Gemini embeddings ({model})")
    return embeddings


# ─────────────────────────────────────────────────────────────────────────
# [OPS:IDX-002] embed_texts() — THE shared embedding entrypoint for the
#                 entire system (the single most-imported function tagged
#                 in this whole codebase)
#
# API/CALL: OpenAI embeddings.create() (_embed_many_openai_impl, batches
#       of 100) OR Gemini embed_content() (_embed_many_gemini_impl,
#       batches of 10 with 429 retry/backoff) — provider priority is
#       OpenAI > Gemini > mock, decided by which API key env var is set.
# KNOWN BUG (documented, not yet fixed): if BOTH OPENAI_API_KEY and
#       GEMINI_API_KEY are set, OpenAI silently wins here — matches the
#       identical bug in [OPS:LLM-001] LLMClient.__init__, so at least
#       the embedding provider and the generation provider stay
#       consistent with each other even when the bug fires.
# WHY THIS FUNCTION MUST STAY THE SINGLE CALL SITE: [OPS:IDX-004]
#       PersistedInMemorySearch (primary index), [OPS:PVEC-003]
#       upsert_documents() (pgvector dual-write), and every query
#       embedding in chat.py/pgvector_store.py all call this exact
#       function — if any of them embedded independently with different
#       settings, the resulting vectors would live in different spaces
#       and cosine similarity between them would be meaningless.
# GEMINI DIMENSION NUANCE: gemini-embedding-001 natively outputs 3072
#       dims; output_dimensionality=1536 (Matryoshka representation
#       learning) truncates to a smaller, still-meaningful vector — done
#       specifically because pgvector's ivfflat/hnsw index types cap at
#       2000 dims, so 1536 keeps a future ANN index viable even though
#       none is active yet (see schema.sql [OPS:SCHEMA] comments).
# CALLED BY: [OPS:CHAT-006]/[OPS:CHAT-007] (query embedding, primary
#       path), [OPS:PVEC-003]/[OPS:PVEC-004]/[OPS:PVEC-006]/[OPS:PVEC-007]
#       (dual-write + every pgvector query embedding), [OPS:IDX-004]
#       ingest_texts() (bulk document embedding at index-build time).
# ─────────────────────────────────────────────────────────────────────────
def embed_texts(texts: List[str], use_mock: Optional[bool] = None) -> List[List[float]]:
    """
    Shared embedding entry point: provider priority OpenAI > Gemini > mock.
    Used by both the primary index (PersistedInMemorySearch) and the
    pgvector fallback (pgvector_store.py) so both paths embed queries in the
    exact same vector space — otherwise their similarity scores would not be
    comparable and the fallback would silently return garbage.
    """
    if use_mock is None:
        has_api_key = bool(os.getenv("OPENAI_API_KEY") or os.getenv("GEMINI_API_KEY"))
        use_mock = os.getenv("USE_MOCK_EMBEDDINGS", "false" if has_api_key else "true").lower() in ("true", "1", "yes")

    if not use_mock and os.getenv("OPENAI_API_KEY"):
        try:
            return _embed_many_openai_impl(texts)
        except Exception as e:
            print(f"[WARN] OpenAI embedding failed: {e}. Falling back to mock embeddings.")
            return [_hash_to_vector(text) for text in texts]

    if not use_mock and os.getenv("GEMINI_API_KEY"):
        try:
            return _embed_many_gemini_impl(texts)
        except Exception as e:
            print(f"[WARN] Gemini embedding failed: {e}. Falling back to mock embeddings.")
            return [_hash_to_vector(text) for text in texts]

    print(f"[INFO] Using mock embeddings for {len(texts)} texts")
    return [_hash_to_vector(text) for text in texts]


# ─────────────────────────────────────────────────────────────────────────
# [OPS:IDX-003] PersistedInMemorySearch.__init__() / _load_if_exists() —
#                 loads the entire index into a Python list on construction
#
# WHAT: reads the whole JSON file into self.items on every construction
#       (no lazy loading, no streaming) — fine at ~117 chunks, would need
#       rethinking at a much larger corpus. Handles TWO index file
#       formats: the current "enhanced_index.json" shape
#       ({"embedding_dim", "documents", "embeddings", "metadata"}, one
#       parallel array per field) and a legacy shape ({"dim", "items"},
#       already the {id, text, metadata, vector} shape this class uses
#       internally) — both get normalized into self.items either way.
# NUANCE: this constructor is called FRESH on every single retrieval
#       request via [OPS:CHAT-006] _get_enhanced_index() — there is no
#       persistent singleton/cache across requests, so index freshness
#       after a reindex is immediate (no stale-cache invalidation logic
#       needed) at the cost of re-reading the file every time.
# CALLED BY: [OPS:CHAT-006] _get_enhanced_index(), once per chat request.
# ─────────────────────────────────────────────────────────────────────────
class PersistedInMemorySearch:
    """
    Tiny file-backed vector store for quick RAG bring-up.
    Uses mock embeddings instead of OpenAI to avoid API costs.
    Stores: [{'id', 'text', 'metadata', 'vector'}]
    """
    def __init__(self, index_path: str | Path = None):
        
        self.index_path = Path(index_path or os.getenv("RAG_INDEX_PATH", "backend/app/features/rag_chatbot/vector/.index.json"))
        self.items: List[Dict[str, Any]] = []
        self.dim: Optional[int] = None
        

        index_path = index_path or os.getenv("RAG_INDEX_PATH")
        if index_path is None:
            # Use enhanced_index.json as default, not index.json
            index_path = Path(__file__).resolve().parent / "enhanced_index.json"
        self.index_path = Path(index_path)
        # Use real embeddings by default if a provider key is available, otherwise mock
        has_api_key = bool(os.getenv("OPENAI_API_KEY") or os.getenv("GEMINI_API_KEY"))
        use_mock_env = os.getenv("USE_MOCK_EMBEDDINGS", "false" if has_api_key else "true").lower()
        self.use_mock = use_mock_env in ("true", "1", "yes")
        
        self._load_if_exists()

    def _embed_many(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for texts. Delegates to the module-level
        embed_texts() so the pgvector fallback path (pgvector_store.py) uses
        the exact same provider/model — otherwise primary and fallback
        results would live in incompatible vector spaces."""
        return embed_texts(texts, use_mock=self.use_mock)

    def _save(self):
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.index_path, "w", encoding="utf-8") as f:
            json.dump({"dim": self.dim, "items": self.items}, f)

    def _load_if_exists(self):
        if self.index_path.exists():
            try:
                data = json.loads(self.index_path.read_text())
                
                # Handle enhanced_index.json format (version 2.0)
                if "embedding_dim" in data and "documents" in data and "embeddings" in data:
                    print(f"[INFO] Loading enhanced index format v{data.get('version', 'unknown')}")
                    self.dim = data.get("embedding_dim")
                    docs = data.get("documents", [])
                    embs = data.get("embeddings", [])
                    metas = data.get("metadata", [])
                    
                    # Convert to items format
                    self.items = []
                    for i, (doc, emb) in enumerate(zip(docs, embs)):
                        meta = metas[i] if i < len(metas) else {}
                        self.items.append({
                            "id": meta.get("id", f"doc-{i}"),
                            "text": doc,
                            "metadata": meta,
                            "vector": emb
                        })
                    print(f"[INFO] Loaded {len(self.items)} items with {self.dim}-dim embeddings")
                    
                # Handle legacy format  
                elif "dim" in data and "items" in data:
                    print(f"[INFO] Loading legacy index format")
                    self.dim = data.get("dim")
                    self.items = data.get("items", [])
                    print(f"[INFO] Loaded {len(self.items)} items with {self.dim}-dim embeddings")
                    
                else:
                    print(f"[WARN] Unknown index format with keys: {list(data.keys())}")
                    self.dim = None
                    self.items = []
                    
            except Exception as e:
                print(f"[ERROR] Failed to load index: {e}")
                self.dim = None
                self.items = []

    # ---------------- public API ----------------

    # ─────────────────────────────────────────────────────────────────
    # [OPS:IDX-004] ingest_texts() / ingest_documents() — bulk embed +
    #                 append + persist to disk
    #
    # WHAT: embeds ALL texts in one embed_texts() call (batched provider-
    #       side, see [OPS:IDX-002]), appends every resulting item to
    #       self.items, then writes the WHOLE index back to disk — not
    #       an incremental/streaming append, so calling this repeatedly
    #       on a large corpus re-serializes the growing file each time.
    # CALLED BY: build_local_index.py [OPS:ING-002], build_drive_index.py
    #       [OPS:DRIVE-003] — the actual index-build entrypoints; this
    #       class's search-time construction [OPS:IDX-003] never calls
    #       ingest_* itself, only reads what's already on disk.
    # ─────────────────────────────────────────────────────────────────
    def ingest_texts(self, texts: List[str], metadatas: Optional[List[Dict[str, Any]]] = None, ids: Optional[List[str]] = None):
        metadatas = metadatas or [{} for _ in texts]
        ids = ids or [f"doc-{i}" for i, _ in enumerate(texts)]
        vectors = self._embed_many(texts)
        if vectors:
            self.dim = len(vectors[0])
        for tid, txt, meta, vec in zip(ids, texts, metadatas, vectors):
            self.items.append({"id": tid, "text": txt, "metadata": meta, "vector": vec})
        self._save()

    def ingest_documents(self, documents: List[Dict[str, Any]]):
        texts = [d["text"] for d in documents]
        metas = [d.get("metadata", {}) for d in documents]
        ids = [documents[i].get("id") or f"doc-{i}" for i in range(len(documents))]
        self.ingest_texts(texts, metas, ids)

    # ─────────────────────────────────────────────────────────────────
    # [OPS:IDX-005] search() — the actual primary-path retrieval:
    #                 brute-force cosine similarity, no ANN index
    #
    # WHAT: embeds the query once, then computes _cosine() [OPS:IDX-001]
    #       against EVERY item in self.items (a full O(n) linear scan —
    #       there is no ivfflat/hnsw-equivalent structure here; "index"
    #       in this class's name means "persisted to disk," not "search
    #       index data structure"), sorts descending, slices top_k.
    # WHY THIS IS FINE TODAY: ~117 chunks means the whole scan is
    #       microseconds — the real cost per request is the single
    #       embedding API call, not the similarity math. Would need
    #       revisiting (numpy vectorized batch dot-product at minimum,
    #       or a real ANN structure) at a meaningfully larger corpus.
    # RETURNS: [{text, score, metadata}] sorted best-first — this exact
    #       ordering is what makes [OPS:CHAT-014]'s greedy token-budget
    #       truncation correct (it assumes best-to-worst order already).
    # CALLED BY: [OPS:CHAT-007] _enhanced_retrieve(), once per request.
    # ─────────────────────────────────────────────────────────────────
    def search(self, query: str, top_k: int = 4) -> List[Dict[str, Any]]:
        if not self.items:
            return []
        qvec = self._embed_many([query])[0]
        scored = []
        for it in self.items:
            score = _cosine(qvec, it["vector"])
            scored.append({
                "text": it["text"],
                "score": float(score),
                "metadata": it.get("metadata", {}) | {"id": it.get("id")}
            })
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:max(1, top_k)]

    # [OPS:IDX-006] get_stats() — index introspection, used by
    # [OPS:CHAT-023]-adjacent admin/status surfaces to report corpus size,
    # dimension, and whether mock embeddings are currently active.
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the indexed documents."""
        return {
            "total_documents": len(self.items),
            "embedding_dimension": self.dim,
            "index_file": str(self.index_path),
            "using_mock_embeddings": self.use_mock or not (os.getenv("OPENAI_API_KEY") or os.getenv("GEMINI_API_KEY")),
            "index_size_kb": round(self.index_path.stat().st_size / 1024, 2) if self.index_path.exists() else 0
        }