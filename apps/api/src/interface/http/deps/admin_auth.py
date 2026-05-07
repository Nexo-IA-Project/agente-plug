from __future__ import annotations

from dataclasses import dataclass

from fastapi import Cookie, Header, HTTPException, status
from jose import JWTError

from shared.adapters.kb.jwt_handler import verify_token
from shared.config.settings import get_settings


@dataclass
class AdminAuth:
    account_id: int
    user_email: str
    user_role: str


async def require_admin(
    authorization: str | None = Header(default=None),
    nexoia_token: str | None = Cookie(default=None),
) -> AdminAuth:
    token: str | None = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ").strip()
    elif nexoia_token:
        token = nexoia_token
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    settings = get_settings()
    try:
        payload = verify_token(token, secret=settings.jwt_secret)
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    return AdminAuth(
        account_id=payload["account_id"],
        user_email=payload["sub"],
        user_role=payload.get("role", "viewer"),
    )
