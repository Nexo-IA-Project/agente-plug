from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4


class EnrollmentStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class EnrollmentStepStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(slots=True)
class FollowupFlow:
    id: UUID
    account_id: UUID
    course_id: UUID
    name: str
    is_active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(slots=True)
class FollowupStep:
    id: UUID
    flow_id: UUID
    position: int
    delay_from_purchase_hours: int
    meta_template_name: str | None
    template_variables: dict
    created_at: datetime
    message_text: str | None = None


@dataclass(slots=True)
class FollowupEnrollment:
    account_id: UUID
    flow_id: UUID
    contact_id: UUID
    conversation_id: str  # chatnexo external conversation ID (string)
    contact_phone: str
    purchase_id: str
    customer_name: str
    product_name: str
    id: UUID = field(default_factory=uuid4)
    status: EnrollmentStatus = EnrollmentStatus.ACTIVE
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True)
class FollowupEnrollmentStep:
    enrollment_id: UUID
    position: int
    delay_from_purchase_hours: int
    meta_template_name: str | None
    template_variables: dict
    id: UUID = field(default_factory=uuid4)
    scheduled_job_id: UUID | None = None
    status: EnrollmentStepStatus = EnrollmentStepStatus.PENDING
    sent_at: datetime | None = None
    message_text: str | None = None
    failure_reason: str | None = None
    flow_step_id: UUID | None = None
