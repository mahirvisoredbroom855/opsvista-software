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
