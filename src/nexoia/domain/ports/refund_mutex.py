from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class RefundMutexPort(Protocol):
    async def acquire(self, account_id: int, contact_id: str, product_id: str) -> bool: ...
    async def release(self, account_id: int, contact_id: str, product_id: str) -> None: ...
