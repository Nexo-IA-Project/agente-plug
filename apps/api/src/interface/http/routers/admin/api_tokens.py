from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from interface.http.deps.admin_auth import AdminAuth
from interface.http.deps.admin_auth import require_admin as _require_admin
from interface.http.deps.admin_auth import require_admin_role as _require_admin_role
from shared.adapters.db.repositories.api_token_repo import ApiTokenRepository
from shared.adapters.db.session import session_scope

router = APIRouter(tags=["admin-api-tokens"])


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
    token_prefix: str | None
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
            token_prefix=t.token_prefix,
            is_active=t.is_active,
            created_at=t.created_at,
            last_used_at=t.last_used_at,
        )
        for t in tokens
    ]


@router.delete("/api-tokens/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_token(
    token_id: uuid.UUID,
    auth: AdminAuth = Depends(_require_admin_role),  # noqa: B008
) -> None:
    async with session_scope() as session:
        repo = ApiTokenRepository(session)
        found = await repo.revoke(token_id=token_id)
        if not found:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="token not found")
        await session.commit()
