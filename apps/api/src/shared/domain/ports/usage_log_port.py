from __future__ import annotations

from typing import Protocol, runtime_checkable
from uuid import UUID


@runtime_checkable
class UsageLogPort(Protocol):
    async def record_no_result(self, account_id: UUID, query: str) -> None: ...
