from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable


@runtime_checkable
class LegalHistoryPort(Protocol):
    async def has_prior_refund_mention(
        self,
        *,
        account_id: int,
        contact_id: str,
        purchase_date: datetime,
    ) -> bool: ...
