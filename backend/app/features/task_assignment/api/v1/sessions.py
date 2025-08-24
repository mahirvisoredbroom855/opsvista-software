# backend/app/features/auth/api/v1/sessions.py
from fastapi import APIRouter, Depends, Response, status
from app.core.auth_deps import get_current_user, UserCtx  # adjust import path if different
from app.core.token_blacklist import add as blacklist_token   # NEW

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,                         # non‑default arg  ➜ comes first
    user: UserCtx = Depends(get_current_user),  # default arg via dependency ➜ comes after
):
    """
    Logs the user out by black‑listing their token (if used) and clearing the auth cookie.
    """
    # 1) server‑side invalidation (skip if you don't need token revocation)
    blacklist_token(user.jti)      # implement however you store JTIs (Redis, DB…)

    # 2) client‑side: remove the cookie so the browser no longer sends it
    response.delete_cookie("access_token")
