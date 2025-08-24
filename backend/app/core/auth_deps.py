from __future__ import annotations

import os
from typing import Optional, Callable, Dict, Any, List

from fastapi import Header, HTTPException, Depends

# pydantic is typically available with FastAPI, but keep a safe fallback
try:
    from pydantic import BaseModel
except Exception:  # pragma: no cover
    class BaseModel:  # type: ignore
        def __init__(self, **data):
            for k, v in data.items():
                setattr(self, k, v)

from app.core.supabase_jwt import verify_supabase_token

# --- Environment switches -----------------------------------------------------

# If true, missing/invalid Authorization will yield a dev user for local work.
ALLOW_DEV_AUTH = os.getenv("ALLOW_DEV_AUTH", "true").lower() in {"1", "true", "yes"}

# If true, prints errors from token verification (helpful for local debugging).
DEBUG_AUTH = os.getenv("DEBUG_AUTH", "false").lower() in {"1", "true", "yes"}

# --- Models -------------------------------------------------------------------

class UserCtx(BaseModel):
    id: str = "dev"
    role: str = "developer"
    email: Optional[str] = None
    app_metadata: Optional[Dict[str, Any]] = None
    raw: Optional[Dict[str, Any]] = None

# --- Helpers ------------------------------------------------------------------

def _build_user(payload: Dict[str, Any]) -> UserCtx:
    app_meta: Dict[str, Any] = payload.get("app_metadata") or {}
    role = app_meta.get("role") or payload.get("role") or "authenticated"
    return UserCtx(
        id=payload.get("sub") or payload.get("user_id") or "unknown",
        role=role,
        email=payload.get("email"),
        app_metadata=app_meta,
        raw=payload,
    )

def _dev_user_or_none() -> Optional[UserCtx]:
    return UserCtx() if ALLOW_DEV_AUTH else None

# --- Dependencies -------------------------------------------------------------

def get_current_user_optional(
    authorization: str | None = Header(default=None),
) -> Optional[UserCtx]:
    """
    Returns a UserCtx if a valid Bearer token is supplied.
    - If no/invalid header: returns a dev user when ALLOW_DEV_AUTH=true, else None.
    """
    if not authorization:
        return _dev_user_or_none()

    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            return _dev_user_or_none()
    except Exception:
        return _dev_user_or_none()

    try:
        payload = verify_supabase_token(token)
        if not isinstance(payload, dict):
            return _dev_user_or_none()
        return _build_user(payload)
    except Exception as e:
        if DEBUG_AUTH:
            print(f"[auth] verify_supabase_token failed: {e!r}")
        return _dev_user_or_none()

def get_current_user(
    user: Optional[UserCtx] = Depends(get_current_user_optional),
) -> UserCtx:
    """
    Strict auth: requires a valid user.
    - When ALLOW_DEV_AUTH=true, this still returns a dev user if no token is present.
      Set ALLOW_DEV_AUTH=false in your environment for truly strict behavior.
    """
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user

def require_roles(roles: List[str]) -> Callable:
    """
    Usage:
        @router.get("/admin")
        def admin_only(_: UserCtx = Depends(require_roles(["admin"]))):
            ...
    """
    def _dep(user: UserCtx = Depends(get_current_user)) -> UserCtx:
        if roles and user.role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient role")
        return user
    return _dep
