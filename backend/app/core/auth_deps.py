"""
This file decides who's allowed to do what. Before any admin page or
admin action runs, one of the functions here checks: is there a valid
login token, and does that person's account have the right role
(Owner or Admin)? There's also a side door for the nightly automatic
reindex job, which has no human logging in, so it proves itself with a
secret key instead of a login.
"""
from __future__ import annotations

import os
import secrets as _secrets
from typing import Optional, List, Callable, Dict, Any
from fastapi import Header, HTTPException, Depends

from app.core.supabase_jwt import verify_supabase_token

# MODULE: [OPS:AUTH] — request-time authentication & role gating
#
# What it does: three layers, each building on the last.
# get_current_user_optional() checks a login token but never rejects
# the request if it's missing. get_current_user() wraps that with a
# hard 401 for routes that require a login. require_roles() adds a
# role check (403) on top. require_roles_or_automation_token() is the
# special case that also accepts a secret key for headless callers
# like the reindex cron job, which has no human login at all.

# ─────────────────────────────────────────────────────────────────────────
# [OPS:AUTH-001] get_current_user_optional()
#
# What it does: reads the "Authorization: Bearer <token>" header and
# asks Supabase to verify it. Any failure at all — missing header,
# wrong format, expired token, Supabase unreachable — just returns
# None, never raises an error. That's what makes this safe to use on
# endpoints that still have to work for people who aren't logged in.
#
# Called by: chat_complete(), chat_stream(), submit_feedback() — and,
# one layer removed, every route using get_current_user() or
# require_roles(), since both depend on this function first.
# ─────────────────────────────────────────────────────────────────────────
# Optional auth dependency: returns payload dict or None
def get_current_user_optional(authorization: str | None = Header(default=None)) -> Optional[Dict[str, Any]]:
    if not authorization:
        return None
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            return None
        payload = verify_supabase_token(token)
        return payload if isinstance(payload, dict) else None
    except Exception:
        # Silent fail (optional)
        return None

# ─────────────────────────────────────────────────────────────────────────
# [OPS:AUTH-003] get_current_user() — the hard-401 variant
#
# What it does: reuses get_current_user_optional() entirely — never
# re-verifies the token itself — and just turns a None result into a
# real 401 error. Because it reuses rather than duplicates the check,
# the optional and strict versions can never disagree about what
# counts as a valid token.
#
# Called by: nothing directly today — every route needing auth also
# needs a role check, so they use require_roles() instead, which
# depends on this.
# ─────────────────────────────────────────────────────────────────────────
# Strict auth (401 if no/invalid token)
def get_current_user(user: Dict[str, Any] | None = Depends(get_current_user_optional)) -> Dict[str, Any]:
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user

# ─────────────────────────────────────────────────────────────────────────
# [OPS:AUTH-004] require_roles() — role-based access control
#
# What it does: this doesn't check anything itself — it BUILDS a
# checking function. Call it once with an allowed role list (e.g.
# require_roles(["Owner","Admin"])) and it hands back a function
# FastAPI can use as a dependency. The actual role comes from a field
# Supabase stores on the user's account, set manually by an Owner —
# there's no self-service way for a user to grant themselves a role.
#
# Called by: admin_metrics.py, gating every metrics route.
# ─────────────────────────────────────────────────────────────────────────
# Role guard (403 if role not allowed)
def require_roles(roles: List[str]) -> Callable:
    def _dep(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
        app_meta = user.get("app_metadata", {}) or {}
        role = app_meta.get("role") or user.get("role")
        if roles and role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient role")
        return user
    return _dep


# ─────────────────────────────────────────────────────────────────────────
# [OPS:AUTH-005] require_roles_or_automation_token()
#
# What it does: same as require_roles(), plus one extra path — a
# secret header ("X-Automation-Token") that, if it matches the
# server's configured value, is accepted immediately without checking
# for a login at all. This exists because the nightly cron job has no
# human account to log in with. The comparison uses a constant-time
# check (secrets.compare_digest) instead of plain "==", so a timing
# attack can't be used to guess the secret one character at a time. If
# the secret env var is never set, this whole path is simply
# unreachable and the endpoint always requires a real login — never
# silently open.
#
# Called by: discovery.py, gating POST /api/rag/admin/reindex — the
# endpoint the nightly GitHub Action calls.
# ─────────────────────────────────────────────────────────────────────────
# Same role guard, but also accepts a static shared-secret header instead of a
# Supabase session — for headless callers (a scheduled reindex cron job) that
# can't hold onto a user session/refresh token. Disabled entirely unless
# REINDEX_AUTOMATION_TOKEN is set; compared with a constant-time check so a
# timing attack can't be used to guess it.
def require_roles_or_automation_token(roles: List[str]) -> Callable:
    def _dep(
        x_automation_token: str | None = Header(default=None, alias="X-Automation-Token"),
        user: Optional[Dict[str, Any]] = Depends(get_current_user_optional),
    ) -> Dict[str, Any]:
        configured_token = os.getenv("REINDEX_AUTOMATION_TOKEN")
        if configured_token and x_automation_token and _secrets.compare_digest(x_automation_token, configured_token):
            return {"id": None, "email": "automation", "app_metadata": {"role": "Automation"}}

        if not user:
            raise HTTPException(status_code=401, detail="Not authenticated")
        app_meta = user.get("app_metadata", {}) or {}
        role = app_meta.get("role") or user.get("role")
        if roles and role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient role")
        return user
    return _dep
