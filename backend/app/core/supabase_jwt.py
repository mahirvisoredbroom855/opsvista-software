# backend/app/core/supabase_jwt.py
"""
This file answers one question: is the login token a request carries
actually real? Rather than checking the token's signature itself (a
"JWT" is just a signed, tamper-proof login pass), it asks Supabase's
own servers to confirm it — slightly slower, but correct no matter how
a given Supabase project happens to sign its tokens.

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


# ─────────────────────────────────────────────────────────────────────────
# [OPS:AUTH-002] _anon_client()
#
# What it does: builds one Supabase client (using the public anon key,
# not the secret service key) and reuses it for every request after the
# first — @lru_cache with no arguments makes this function only ever
# actually run once per server process. If the URL or key env vars
# aren't set, it returns None instead of crashing.
#
# Called by: get_current_user_optional(), every time it needs to check a
# token.
# ─────────────────────────────────────────────────────────────────────────
@lru_cache()
def _anon_client():
    from supabase import create_client

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_ANON_KEY")
    if not url or not key or "placeholder" in url:
        return None
    return create_client(url, key)


# [OPS:AUTH-002b] verify_supabase_token()
#
# What it does: sends the token to Supabase's own servers and asks "is
# this real, and who is it?" instead of checking the signature locally.
# Any problem — expired, malformed, revoked, or Supabase itself being
# down — raises a 401 error here. It's the caller,
# get_current_user_optional(), that catches that error and turns it into
# a quiet "treat this person as not logged in" instead of crashing the
# request.
#
# Called by: get_current_user_optional(), on every request that carries
# a login token.
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
