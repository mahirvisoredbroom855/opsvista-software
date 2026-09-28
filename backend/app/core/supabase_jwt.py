# backend/app/core/supabase_jwt.py
"""
Access-token verification for Supabase Auth.

Deliberately does NOT hand-roll JWT signature verification (the previous
version decoded HS256 tokens against SUPABASE_JWT_SECRET locally, and would
crash the entire app at import time if that env var was unset). Supabase
projects created under the newer key system may not use a static HS256
secret at all — so instead this asks Supabase's own Auth API to validate the
token, which is correct regardless of the project's signing scheme and is
the officially supported verification path (client.auth.get_user(token)).

Trade-off: one extra network round-trip per authenticated request instead
of local crypto verification. For this app's traffic volume that's a
non-issue; if it ever matters, swap in JWKS-based local verification then.
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Any, Dict

from fastapi import HTTPException


# ═══════════════════════════════════════════════════════════════════════
# MODULE: [OPS:AUTH-002] — Supabase token verification (NOT local JWT decode)
#
# WHAT: _anon_client() is memoized (@lru_cache, zero-arg — effectively a
#       process-wide singleton) since it's constructed fresh on every
#       cold import otherwise; safe to cache because SUPABASE_URL/ANON_KEY
#       don't change at runtime.
# WHY client.auth.get_user(token) INSTEAD OF LOCAL HS256 VERIFICATION:
#       the prior version decoded tokens locally against
#       SUPABASE_JWT_SECRET and crashed the whole app at import time if
#       that env var was unset; newer Supabase projects may not even use
#       a static HS256 secret. Asking Supabase's own Auth API to validate
#       is correct regardless of signing scheme — at the cost of one
#       extra network round-trip per authenticated request (acceptable
#       at this app's traffic volume).
# CALLED BY: [OPS:AUTH-001] get_current_user_optional() — the sole call
#       site; every authenticated route path funnels through there first.
# ═══════════════════════════════════════════════════════════════════════
@lru_cache()
def _anon_client():
    from supabase import create_client

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_ANON_KEY")
    if not url or not key or "placeholder" in url:
        return None
    return create_client(url, key)


# [OPS:AUTH-002b] verify_supabase_token() — API/CALL: Supabase Auth
# get_user(token). Raises HTTPException(401) on ANY failure (expired,
# malformed, revoked, or Supabase unreachable) rather than returning
# None — the caller, get_current_user_optional() [OPS:AUTH-001], is what
# converts that into a soft "anonymous" fallback for optional-auth routes.
def verify_supabase_token(token: str) -> Dict[str, Any]:
    """Validate an access token against Supabase Auth and return the user
    payload (dict with at least "id" and "email"). Raises HTTPException(401)
    on any failure — expired, malformed, revoked, or Supabase unreachable."""
    client = _anon_client()
    if client is None:
        raise HTTPException(status_code=401, detail="Auth not configured")

    try:
        resp = client.auth.get_user(token)
        user = resp.user
        if not user:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        return {
            "id": user.id,
            "email": user.email,
            "app_metadata": user.app_metadata or {},
            "user_metadata": user.user_metadata or {},
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid or expired Supabase token: {e}")
