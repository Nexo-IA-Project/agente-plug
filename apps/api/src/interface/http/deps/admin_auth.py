from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from fastapi import Cookie, Depends, Header, HTTPException, Query, Request, status
from jose import JWTError

from shared.adapters.kb.jwt_handler import verify_token
from shared.config.settings import get_settings


@dataclass
class AdminAuth:
    account_id: UUID | None
    user_email: str
    user_role: str
    user_id: str  # = identity_id (compat)
    identity_id: str
    membership_id: str | None
    user_name: str
    must_change_password: bool


def _verify(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        return verify_token(token, secret=settings.jwt_secret)
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def _payload_to_auth(payload: dict[str, Any]) -> AdminAuth:
    # account_id agora é UUID. Tokens legados (emitidos antes da migração)
    # carregavam um inteiro — toleramos: parse falho → None, sem derrubar o login.
    raw_acc = payload.get("account_id")
    try:
        account_id = UUID(str(raw_acc)) if raw_acc is not None else None
    except (ValueError, TypeError):
        account_id = None

    email = payload["sub"]
    identity_id = payload.get("identity_id") or payload.get("user_id", "")
    return AdminAuth(
        account_id=account_id,
        user_email=email,
        user_role=payload.get("role", "operator"),
        user_id=identity_id,
        identity_id=identity_id,
        membership_id=payload.get("membership_id"),
        user_name=payload.get("user_name") or email,
        must_change_password=payload.get("must_change_password", False),
    )


def _decode(token: str) -> AdminAuth:
    """Decodifica um token COMPLETO. Rejeita tokens pre_auth (escopo mínimo).

    Tokens com `scope == "pre_auth"` só servem para `select-account` e para a
    troca obrigatória de senha. Aceitá-los aqui permitiria burlar o
    `must_change_password` (via switch-account) e acessar dados sob a conta
    default. Por isso, 403 explícito.
    """
    payload = _verify(token)
    if payload.get("scope") == "pre_auth":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token de pré-autenticação não autorizado aqui",
        )
    return _payload_to_auth(payload)


async def require_admin(
    request: Request,
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
    auth = _decode(token)
    request.state.audit_ctx = {
        "account_id": auth.account_id,
        "user_id": auth.user_id,
        "user_email": auth.user_email,
        "user_name": auth.user_name,
    }
    return auth


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


@dataclass
class PasswordChangeIdentity:
    identity_id: str
    is_pre_auth: bool


async def require_identity_for_password_change(
    request: Request,
    authorization: str | None = Header(default=None),
    nexoia_token: str | None = Cookie(default=None),
) -> PasswordChangeIdentity:
    """Identidade para troca de senha — aceita token COMPLETO ou pre_auth.

    Este é o ÚNICO endpoint de dados que aceita pre_auth, porque o fluxo de
    `must_change_password` no login retorna pre_auth e o usuário precisa trocar
    a senha antes de obter um token completo. Demais endpoints usam
    `require_admin`, que rejeita pre_auth.
    """
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
    payload = _verify(token)
    identity_id = payload.get("identity_id") or payload.get("user_id", "")
    if not identity_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")
    return PasswordChangeIdentity(
        identity_id=str(identity_id),
        is_pre_auth=payload.get("scope") == "pre_auth",
    )
