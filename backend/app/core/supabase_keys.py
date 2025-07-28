import os, time, httpx
from typing import Dict, Any, Optional

JWKS_URL = os.getenv("SUPABASE_URL", "").rstrip("/") + "/auth/v1/keys"
_CACHE_TTL = 300
_cached: Optional[Dict[str, Any]] = None
_cached_at = 0.0

def _download() -> Dict[str, Any]:
    if not JWKS_URL:
        raise RuntimeError("SUPABASE_URL env var missing")
    r = httpx.get(JWKS_URL, timeout=10)
    r.raise_for_status()
    return r.json()

def get_key(kid: str) -> Optional[Dict[str, Any]]:
    global _cached, _cached_at
    now = time.time()
    if _cached is None or now - _cached_at > _CACHE_TTL:
        _cached, _cached_at = _download(), now
    for k in _cached["keys"]:
        if k.get("kid") == kid:
            return k
    _cached, _cached_at = _download(), now
    for k in _cached["keys"]:
        if k.get("kid") == kid:
            return k
    return None
