from __future__ import annotations

from datetime import datetime
from uuid import UUID

from cryptography.fernet import Fernet
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from interface.http.deps.admin_auth import AdminAuth, require_admin
from shared.adapters.db.repositories.chatnexo_agent_repo import (
    ChatNexoAgentRepository,
    _decrypt,
    _mask,
)
from shared.adapters.db.session import session_scope
from shared.config.settings import get_settings
from shared.config.single_tenant import get_default_account_uuid

router = APIRouter(tags=["admin-chatnexo-agents"])


class AgentItem(BaseModel):
    id: UUID
    name: str
    api_key_masked: str
    is_active: bool
    created_at: datetime


class CreateAgentInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    api_key: str = Field(min_length=1)


class UpdateAgentInput(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    api_key: str | None = Field(default=None, min_length=1)
    is_active: bool | None = None


def _fernet() -> Fernet:
    return Fernet(get_settings().integration_credentials_key.encode())


@router.get("/chatnexo-agents", response_model=list[AgentItem])
async def list_agents(_auth: AdminAuth = Depends(require_admin)) -> list[AgentItem]:  # noqa: B008
    async with session_scope() as session:
        fernet = _fernet()
        repo = ChatNexoAgentRepository(session=session, fernet=fernet)
        account_id = await get_default_account_uuid(session)
        models = await repo.list_all(account_id)
        return [
            AgentItem(
                id=m.id,
                name=m.name,
                api_key_masked=_mask(_decrypt(fernet, m.api_key_encrypted)),
                is_active=m.is_active,
                created_at=m.created_at,
            )
            for m in models
        ]


@router.post("/chatnexo-agents", response_model=AgentItem, status_code=status.HTTP_201_CREATED)
async def create_agent(
    body: CreateAgentInput,
    _auth: AdminAuth = Depends(require_admin),  # noqa: B008
) -> AgentItem:
    async with session_scope() as session:
        fernet = _fernet()
        repo = ChatNexoAgentRepository(session=session, fernet=fernet)
        account_id = await get_default_account_uuid(session)
        agent = await repo.create(account_id=account_id, name=body.name, api_key=body.api_key)
        return AgentItem(
            id=agent.id,
            name=agent.name,
            api_key_masked=_mask(agent.api_key),
            is_active=agent.is_active,
            created_at=agent.created_at or datetime.utcnow(),
        )


@router.patch("/chatnexo-agents/{agent_id}", response_model=AgentItem)
async def update_agent(
    agent_id: UUID,
    body: UpdateAgentInput,
    _auth: AdminAuth = Depends(require_admin),  # noqa: B008
) -> AgentItem:
    if body.name is None and body.api_key is None and body.is_active is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Forneça pelo menos um campo para atualizar (name, api_key ou is_active).",
        )
    async with session_scope() as session:
        fernet = _fernet()
        repo = ChatNexoAgentRepository(session=session, fernet=fernet)
        account_id = await get_default_account_uuid(session)
        try:
            agent = await repo.update(
                id=agent_id,
                account_id=account_id,
                name=body.name,
                api_key=body.api_key,
                is_active=body.is_active,
            )
        except KeyError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Agente não encontrado"
            ) from exc
        return AgentItem(
            id=agent.id,
            name=agent.name,
            api_key_masked=_mask(agent.api_key),
            is_active=agent.is_active,
            created_at=agent.created_at or datetime.utcnow(),
        )


@router.delete("/chatnexo-agents/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(agent_id: UUID, _auth: AdminAuth = Depends(require_admin)) -> None:  # noqa: B008
    async with session_scope() as session:
        fernet = _fernet()
        repo = ChatNexoAgentRepository(session=session, fernet=fernet)
        account_id = await get_default_account_uuid(session)
        try:
            await repo.delete(id=agent_id, account_id=account_id)
        except KeyError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Agente não encontrado"
            ) from exc
