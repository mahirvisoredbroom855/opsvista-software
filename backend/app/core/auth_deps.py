from __future__ import annotations

import os
import secrets as _secrets
from typing import Optional, List, Callable, Dict, Any
from fastapi import Header, HTTPException, Depends

from app.core.supabase_jwt import verify_supabase_token

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

# Strict auth (401 if no/invalid token)
def get_current_user(user: Dict[str, Any] | None = Depends(get_current_user_optional)) -> Dict[str, Any]:
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user

# Role guard (403 if role not allowed)
def require_roles(roles: List[str]) -> Callable:
    def _dep(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
        app_meta = user.get("app_metadata", {}) or {}
        role = app_meta.get("role") or user.get("role")
        if roles and role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient role")
        return user
    return _dep


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
