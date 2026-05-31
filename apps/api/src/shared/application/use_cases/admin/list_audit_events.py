from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from shared.domain.entities.audit_event import AuditEvent
from shared.domain.ports.audit_repository import AuditRepository


@dataclass
class ListAuditEventsInput:
    account_id: UUID
    user_id: str | None = None
    action: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    page: int = 1
    page_size: int = 25


@dataclass
class ListAuditEventsOutput:
    items: list[AuditEvent]
    total: int
    page: int
    page_size: int


class ListAuditEventsUseCase:
    def __init__(self, *, repo: AuditRepository) -> None:
        self._repo = repo

    async def execute(self, inp: ListAuditEventsInput) -> ListAuditEventsOutput:
        page_size = min(inp.page_size, 100)
        items, total = await self._repo.paginate(
            inp.account_id,
            user_id=inp.user_id,
            action=inp.action,
            date_from=inp.date_from,
            date_to=inp.date_to,
            page=inp.page,
            page_size=page_size,
        )
        return ListAuditEventsOutput(
            items=items,
            total=total,
            page=inp.page,
            page_size=page_size,
        )
