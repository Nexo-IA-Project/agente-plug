from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol
from uuid import UUID

_CDC_WINDOW_DAYS = 7


class MessageRepoProto(Protocol):
    async def find_refund_mentions(
        self,
        *,
        account_id: UUID,
        contact_id: UUID,
        window_start: datetime,
        window_end: datetime,
    ) -> list[str]: ...


@dataclass
class LegalHistoryChecker:
    """Checks if contact mentioned refund/cancellation within the 7-day CDC window.

    Used by Refund capability (spec ④) node `check_deadline` to force
    `within_deadline = True` when student requested before on any channel.
    """

    message_repo: MessageRepoProto

    async def has_prior_refund_mention(
        self,
        *,
        account_id: UUID,
        contact_id: UUID,
        purchase_date: datetime,
    ) -> bool:
        mentions = await self.message_repo.find_refund_mentions(
            account_id=account_id,
            contact_id=contact_id,
            window_start=purchase_date,
            window_end=purchase_date + timedelta(days=_CDC_WINDOW_DAYS),
        )
        return len(mentions) > 0
