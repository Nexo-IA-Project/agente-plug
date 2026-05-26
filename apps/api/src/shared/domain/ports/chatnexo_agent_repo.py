from __future__ import annotations

from typing import Protocol
from uuid import UUID

from shared.domain.entities.chatnexo_agent import ChatNexoAgent


class ChatNexoAgentRepositoryPort(Protocol):
    async def list_active(self, account_id: UUID) -> list[ChatNexoAgent]: ...
    async def create(self, *, account_id: UUID, name: str, api_key: str) -> ChatNexoAgent: ...
    async def update(
        self, *, id: UUID, account_id: UUID, name: str | None, api_key: str | None, is_active: bool | None
    ) -> ChatNexoAgent: ...
    async def delete(self, *, id: UUID, account_id: UUID) -> None: ...
