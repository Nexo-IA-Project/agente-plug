from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class HublaPurchase:
    id: str
    product_name: str
    created_at: datetime
    amount: float
    is_duplicate: bool
    is_recurring: bool
    first_charge_at: datetime | None


@dataclass(frozen=True)
class RefundResult:
    success: bool
    refund_id: str | None
    error: str | None


@runtime_checkable
class HublaPort(Protocol):
    async def get_purchase_by_email(self, email: str, account_id: int) -> HublaPurchase | None: ...
    async def process_refund(self, purchase_id: str, reason: str) -> RefundResult: ...
