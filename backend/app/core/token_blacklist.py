# backend/app/core/token_blacklist.py
from typing import Set
import threading

_lock = threading.Lock()
_revoked: Set[str] = set()        # in‑memory demo; switch to Redis or DB in prod

def add(jti: str) -> None:
    with _lock:
        _revoked.add(jti)

def is_revoked(jti: str) -> bool:
    with _lock:
        return jti in _revoked
