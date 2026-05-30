from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4


class AccessCaseStatus(StrEnum):
    PENDING = "pending"
    LINK_SENT = "link_sent_proativo"
    ACCESSED = "accessed"
    REMINDED_D1 = "reminded_d1"
    ESCALATED = "escalated"
    REACTIVE_LINK_SENT = "reactive_link_sent"
    REACTIVE_ESCALATED = "reactive_escalated"


@dataclass
class AccessCase:
    account_id: UUID
    contact_id: str
    conversation_id: str
    purchase_id: str
    product_name: str
    id: str = field(default_factory=lambda: str(uuid4()))
    access_link: str | None = None
    status: AccessCaseStatus = AccessCaseStatus.PENDING
    access_confirmed: bool = False
    scheduled_d1_job_id: str | None = None
    student_cpf: str | None = None
    search_attempts: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
