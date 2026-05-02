from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4


class RefundCaseStatus(StrEnum):
    COLLECTING = "collecting"
    CHECKING_DEADLINE = "checking_deadline"
    IN_RETENTION = "in_retention"
    OFFER_ACCEPTED = "offer_accepted"
    REFUNDED = "refunded"
    DENIED = "denied"
    ESCALATED = "escalated"


@dataclass
class RefundCase:
    account_id: int
    contact_id: str
    conversation_id: str
    student_email: str
    id: str = field(default_factory=lambda: str(uuid4()))
    purchase_id: str | None = None
    product_name: str | None = None
    student_cpf: str | None = None
    refund_reason: str | None = None
    days_since_purchase: int | None = None
    within_deadline: bool | None = None
    is_duplicate_purchase: bool = False
    offers_made: list[str] = field(default_factory=list)
    offer_accepted: bool = False
    refund_processed_this_turn: bool = False
    status: RefundCaseStatus = RefundCaseStatus.COLLECTING
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
