from __future__ import annotations

import os
import secrets as _secrets
from typing import Optional, List, Callable, Dict, Any
from fastapi import Header, HTTPException, Depends

from app.core.supabase_jwt import verify_supabase_token

# ═══════════════════════════════════════════════════════════════════════
# MODULE: [OPS:AUTH] — request-time authentication & role gating
#
# Three layers, each building on the last: [OPS:AUTH-001] extracts and
# verifies a bearer token WITHOUT rejecting the request if it's missing
# (used for endpoints that work anonymously but personalize when logged
# in, e.g. chat_complete()'s user_id); [OPS:AUTH-003] wraps that with a
# hard 401 for routes that require a session; [OPS:AUTH-004] adds role
# checking (403) on top of that; [OPS:AUTH-005] is the special case that
# also accepts a static automation token for headless callers like the
# reindex cron job, which can't hold a Supabase session at all.
# ═══════════════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────────────────
# [OPS:AUTH-001] get_current_user_optional() — FastAPI Depends() dependency,
#                 the root of every auth check in this codebase
#
# API/CALL: [OPS:AUTH-002] verify_supabase_token() — a full Supabase Auth
#       API round-trip, not local JWT decoding.
# WHAT: parses "Authorization: Bearer <token>" manually via str.split()
#       (not FastAPI's OAuth2PasswordBearer — this app doesn't use OAuth2
#       password flow, just raw bearer tokens issued by Supabase client-
#       side auth). ANY failure — missing header, wrong scheme, malformed
#       token, expired token, Supabase unreachable — is swallowed into a
#       plain None return, never an exception. That's what makes this
#       dependency safe to use on endpoints that must still work for
#       anonymous callers.
# CALLED BY (via Depends()): [OPS:CHAT-015] chat_complete(),
#       [OPS:CHAT-020] chat_stream(), [OPS:CHAT-021] submit_feedback(),
#       and — one layer removed — every route using [OPS:AUTH-003]
#       get_current_user() or [OPS:AUTH-004] require_roles(), since both
#       depend on this function first.
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
# WHAT: a thin Depends()-on-Depends() wrapper — reuses [OPS:AUTH-001]
#       entirely rather than re-verifying, and just turns its "None"
#       outcome into an actual HTTPException. This dependency-chaining
#       pattern (rather than a separate strict verification path) is
#       what keeps the two auth modes from ever disagreeing about what
#       counts as a valid token.
# CALLED BY: any endpoint requiring a logged-in user but no specific
#       role (none currently in this codebase call it directly — routes
#       needing auth all also need a role check, so they use
#       [OPS:AUTH-004] require_roles() instead, which depends on this).
# ─────────────────────────────────────────────────────────────────────────
# Strict auth (401 if no/invalid token)
def get_current_user(user: Dict[str, Any] | None = Depends(get_current_user_optional)) -> Dict[str, Any]:
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user

# ─────────────────────────────────────────────────────────────────────────
# [OPS:AUTH-004] require_roles() — role-based access control (RBAC),
#                 returns a Depends()-able closure
#
# WHAT: a dependency FACTORY, not a dependency itself — called once at
#       router-definition time with the allowed role list
#       (e.g. require_roles(["Owner", "Admin"])), producing a function
#       FastAPI can actually use with Depends(). Role comes from Supabase
#       app_metadata.role (set via
#       supabase.auth.admin.update_user_by_id(), an out-of-band admin
#       action — there's no self-service role assignment in this app).
# CALLED BY: [OPS:ADMIN-002] admin_metrics.py's _require_admin =
#       require_roles(["Owner", "Admin"]) — evaluated once at import
#       time and reused across all metrics routes.
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
# [OPS:AUTH-005] require_roles_or_automation_token() — RBAC + headless
#                 automation escape hatch
#
# WHAT: same shape/purpose as [OPS:AUTH-004] require_roles(), plus one
#       extra path: a static shared-secret header
#       ("X-Automation-Token") that, if it matches REINDEX_AUTOMATION_
#       TOKEN, short-circuits straight to an approved response WITHOUT
#       ever calling get_current_user_optional() — because the caller
#       (a GitHub Actions cron job) has no Supabase session to present.
# SECURITY NUANCE: uses secrets.compare_digest() (constant-time
#       comparison), not `==`, specifically so response-time can't leak
#       how many leading characters of the token matched — a standard
#       timing-attack mitigation for secret comparison.
# BREAKS IF: REINDEX_AUTOMATION_TOKEN is unset — the whole automation
#       branch is then unreachable (configured_token is falsy), so a
#       misconfigured deployment safely falls through to requiring a
#       real user session, never silently open.
# CALLED BY: [OPS:ADMIN-001] discovery.py's
#       _require_admin = require_roles_or_automation_token(["Owner", "Admin"])
#       — used by POST /api/rag/admin/reindex, the endpoint the
#       scheduled-reindex.yml GitHub Action [OPS:CI-001] actually calls.
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
