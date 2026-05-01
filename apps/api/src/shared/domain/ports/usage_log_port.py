from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class UsageLogPort(Protocol):
    async def record_no_result(self, account_id: int, query: str) -> None: ...
