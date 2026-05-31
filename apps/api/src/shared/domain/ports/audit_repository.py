from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from shared.domain.entities.audit_event import AuditEvent


class AuditRepository(Protocol):
    async def save(self, event: AuditEvent) -> None: ...

    async def update_geo(
        self,
        event_id: UUID,
        *,
        city: str,
        country: str,
        region: str,
    ) -> None: ...

    async def paginate(
        self,
        account_id: UUID,
        *,
        user_id: str | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        exclude_auth: bool = False,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        page: int = 1,
        page_size: int = 25,
    ) -> tuple[list[AuditEvent], int]: ...
