from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID


class ContactFactsRepo(Protocol):
    async def get_facts(self, *, account_id: UUID, contact_id: UUID) -> dict[str, Any]: ...
    async def update_facts(
        self, *, account_id: UUID, contact_id: UUID, facts: dict[str, Any]
    ) -> None: ...


@dataclass
class LongTermMemory:
    repo: ContactFactsRepo

    async def get(self, *, account_id: UUID, contact_id: UUID) -> dict[str, Any]:
        return await self.repo.get_facts(account_id=account_id, contact_id=contact_id)

    async def update(self, *, account_id: UUID, contact_id: UUID, facts: dict[str, Any]) -> None:
        current = await self.repo.get_facts(account_id=account_id, contact_id=contact_id)
        merged = {**current, **facts}
        await self.repo.update_facts(account_id=account_id, contact_id=contact_id, facts=merged)
