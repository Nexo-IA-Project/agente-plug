from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from cryptography.fernet import Fernet
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.adapters.db.models import ChatNexoAgentModel
from shared.domain.entities.chatnexo_agent import ChatNexoAgent


def _decrypt(fernet: Fernet, value: str) -> str:
    try:
        return fernet.decrypt(value.encode()).decode()
    except Exception:
        return ""


def _encrypt(fernet: Fernet, value: str) -> str:
    return fernet.encrypt(value.encode()).decode()


def _mask(value: str) -> str:
    if not value:
        return "****"
    if len(value) < 8:
        return "****"
    return value[:8] + "****"


def _to_entity(model: ChatNexoAgentModel, fernet: Fernet) -> ChatNexoAgent:
    return ChatNexoAgent(
        id=model.id,
        name=model.name,
        api_key=_decrypt(fernet, model.api_key_encrypted),
        is_active=model.is_active,
        created_at=model.created_at,
    )


@dataclass
class ChatNexoAgentRepository:
    session: AsyncSession
    fernet: Fernet

    async def list_active(self, account_id: UUID) -> list[ChatNexoAgent]:
        stmt = select(ChatNexoAgentModel).where(
            ChatNexoAgentModel.account_id == account_id,
            ChatNexoAgentModel.is_active.is_(True),
        )
        result = await self.session.execute(stmt)
        return [_to_entity(m, self.fernet) for m in result.scalars().all()]

    async def list_all(self, account_id: UUID) -> list[ChatNexoAgentModel]:
        """Retorna modelos crus para exibição admin (chave mascarada pelo router)."""
        stmt = (
            select(ChatNexoAgentModel)
            .where(ChatNexoAgentModel.account_id == account_id)
            .order_by(ChatNexoAgentModel.created_at)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, *, account_id: UUID, name: str, api_key: str) -> ChatNexoAgent:
        model = ChatNexoAgentModel(
            account_id=account_id,
            name=name,
            api_key_encrypted=_encrypt(self.fernet, api_key),
            is_active=True,
        )
        self.session.add(model)
        await self.session.flush()
        return _to_entity(model, self.fernet)

    async def update(
        self,
        *,
        id: UUID,
        account_id: UUID,
        name: str | None,
        api_key: str | None,
        is_active: bool | None = None,
    ) -> ChatNexoAgent:
        stmt = select(ChatNexoAgentModel).where(
            ChatNexoAgentModel.id == id,
            ChatNexoAgentModel.account_id == account_id,
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agente não encontrado")
        if name is not None:
            model.name = name
        if api_key is not None:
            model.api_key_encrypted = _encrypt(self.fernet, api_key)
        if is_active is not None:
            model.is_active = is_active
        await self.session.flush()
        return _to_entity(model, self.fernet)

    async def delete(self, *, id: UUID, account_id: UUID) -> None:
        stmt = select(ChatNexoAgentModel).where(
            ChatNexoAgentModel.id == id,
            ChatNexoAgentModel.account_id == account_id,
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agente não encontrado")
        await self.session.delete(model)
        await self.session.flush()
