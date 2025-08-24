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
        # Use real embeddings by default if API key is available, otherwise mock
        has_api_key = bool(os.getenv("OPENAI_API_KEY"))
        use_mock_env = os.getenv("USE_MOCK_EMBEDDINGS", "false" if has_api_key else "true").lower()
        self.use_mock = use_mock_env in ("true", "1", "yes")
        
        self._load_if_exists()

    def _embed_many(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for texts. Now uses OpenAI by default when API key is available.
        """
        # Check if we should use real OpenAI embeddings
        if not self.use_mock and os.getenv("OPENAI_API_KEY"):
            try:
                from openai import OpenAI
                client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
                
                # Batch process to handle rate limits
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
                
            except Exception as e:
                print(f"[WARN] OpenAI embedding failed: {e}. Falling back to mock embeddings.")
                return [_hash_to_vector(text) for text in texts]
        else:
            print(f"[INFO] Using mock embeddings for {len(texts)} texts")
            return [_hash_to_vector(text) for text in texts]

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

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the indexed documents."""
        return {
            "total_documents": len(self.items),
            "embedding_dimension": self.dim,
            "index_file": str(self.index_path),
            "using_mock_embeddings": self.use_mock or not os.getenv("OPENAI_API_KEY"),
            "index_size_kb": round(self.index_path.stat().st_size / 1024, 2) if self.index_path.exists() else 0
        }