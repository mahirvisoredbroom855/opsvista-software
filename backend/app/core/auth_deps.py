<<<<<<< HEAD
from __future__ import annotations

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
=======
from fastapi import Header, HTTPException, Depends
from pydantic import BaseModel
from app.core.supabase_jwt import verify_supabase_token

class UserCtx(BaseModel):
    id: str
    role: str
    email: str | None = None

def get_current_user(authorization: str = Header(...)) -> UserCtx:
    print("🔐 Authorization header received:", authorization)

    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise ValueError
    except ValueError:
        print("❌ Invalid or missing Bearer token format")
        raise HTTPException(401, "Missing or invalid Bearer token")

    payload = verify_supabase_token(token)
    print("✅ JWT Decoded payload:", payload)

    # 🔎 Extract role safely from app_metadata
    app_meta = payload.get("app_metadata", {})
    role_from_meta = app_meta.get("role")
    fallback_role = payload.get("role", "authenticated")
    role = role_from_meta or fallback_role

    print(f"🎭 Extracted role: {role} (from {'app_metadata' if role_from_meta else 'payload'})")

    return UserCtx(
        id=payload.get("sub"),
        role=role,
        email=payload.get("email"),
    )
>>>>>>> origin/feat/finances-dashboard
