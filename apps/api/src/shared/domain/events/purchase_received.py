from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class PurchaseReceived:
    purchase_id: str
    account_id: UUID
    customer_name: str
    contact_email: str
    contact_phone: str
    product_id: str
    product_name: str
    amount_brl: int
    occurred_at: datetime
