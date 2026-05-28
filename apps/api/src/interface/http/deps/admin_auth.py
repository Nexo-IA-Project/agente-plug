from __future__ import annotations

from dataclasses import dataclass

from fastapi import Cookie, Depends, Header, HTTPException, Query, status
from jose import JWTError

from shared.adapters.kb.jwt_handler import verify_token
from shared.config.settings import get_settings


@dataclass
class AdminAuth:
    account_id: int
    user_email: str
    user_role: str
    user_id: str
    must_change_password: bool


def _decode(token: str) -> AdminAuth:
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
        user_role=payload.get("role", "operator"),
        user_id=payload.get("user_id", ""),
        must_change_password=payload.get("must_change_password", False),
    )


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
    return _decode(token)


async def require_admin_role(
    auth: AdminAuth = Depends(require_admin),
) -> AdminAuth:
    """Strict admin role. 403 for operator users."""
    if auth.user_role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return auth


async def require_admin_sse(
    token: str | None = Query(default=None),
    authorization: str | None = Header(default=None),
    nexoia_token: str | None = Cookie(default=None),
) -> AdminAuth:
    """Variante de require_admin específica pra SSE.

    EventSource não suporta header `Authorization` e nem sempre carrega
    cookies em cross-origin (SameSite=Lax). Esta dependência aceita o JWT
    também via query string `?token=<jwt>` — passar token na URL é
    aceitável aqui porque é só pra endpoint SSE de leitura.
    """
    actual: str | None = None
    if authorization and authorization.startswith("Bearer "):
        actual = authorization.removeprefix("Bearer ").strip()
    elif nexoia_token:
        actual = nexoia_token
    elif token:
        actual = token.strip()
    if not actual:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _decode(actual)
