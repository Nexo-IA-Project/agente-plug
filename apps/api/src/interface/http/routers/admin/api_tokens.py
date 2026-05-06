from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, status
from jose import JWTError
from pydantic import BaseModel

from shared.adapters.db.repositories.api_token_repo import ApiTokenRepository
from shared.adapters.db.session import session_scope
from shared.adapters.kb.jwt_handler import verify_token
from shared.config.settings import get_settings

router = APIRouter(tags=["admin-api-tokens"])


@dataclass
class AdminAuth:
    account_id: int
    user_email: str
    user_role: str


async def _require_admin(
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


class CreateTokenRequest(BaseModel):
    name: str


class TokenCreatedResponse(BaseModel):
    id: uuid.UUID
    name: str
    raw_token: str
    is_active: bool
    created_at: datetime | None


class TokenListItem(BaseModel):
    id: uuid.UUID
    name: str
    is_active: bool
    created_at: datetime | None
    last_used_at: datetime | None


@router.post(
    "/api-tokens", response_model=TokenCreatedResponse, status_code=status.HTTP_201_CREATED
)
async def create_token(
    body: CreateTokenRequest,
    auth: AdminAuth = Depends(_require_admin),  # noqa: B008
) -> TokenCreatedResponse:
    async with session_scope() as session:
        repo = ApiTokenRepository(session)
        model, raw_token = await repo.create(name=body.name)
        await session.commit()
    return TokenCreatedResponse(
        id=model.id,
        name=model.name,
        raw_token=raw_token,
        is_active=model.is_active,
        created_at=model.created_at,
    )


@router.get("/api-tokens", response_model=list[TokenListItem])
async def list_tokens(
    auth: AdminAuth = Depends(_require_admin),  # noqa: B008
) -> list[TokenListItem]:
    async with session_scope() as session:
        repo = ApiTokenRepository(session)
        tokens = await repo.list_all()
    return [
        TokenListItem(
            id=t.id,
            name=t.name,
            is_active=t.is_active,
            created_at=t.created_at,
            last_used_at=t.last_used_at,
        )
        for t in tokens
    ]


@router.delete("/api-tokens/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_token(
    token_id: uuid.UUID,
    auth: AdminAuth = Depends(_require_admin),  # noqa: B008
) -> None:
    async with session_scope() as session:
        repo = ApiTokenRepository(session)
        found = await repo.revoke(token_id=token_id)
        if not found:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="token not found")
        await session.commit()
