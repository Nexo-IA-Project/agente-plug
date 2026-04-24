from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID


class JobType(StrEnum):
    IDLE_PING = "idle_ping"
    IDLE_CLOSE = "idle_close"
    FOLLOWUP_D1 = "followup_d1"
    FOLLOWUP_CUSTOM = "followup_custom"


class JobStatus(StrEnum):
    PENDING = "pending"
    CANCELLED = "cancelled"
    EXECUTED = "executed"
    FAILED = "failed"


@dataclass(slots=True)
class ScheduledJob:
    id: UUID
    account_id: UUID
    conversation_id: UUID | None
    job_type: JobType
    payload: dict[str, Any]
    run_at: datetime
    status: JobStatus = JobStatus.PENDING
    attempts: int = 0
    correlation_id: str | None = None
    created_at: datetime | None = None
    executed_at: datetime | None = None

    def cancel(self) -> None:
        self.status = JobStatus.CANCELLED

    def mark_executed(self, *, at: datetime) -> None:
        self.status = JobStatus.EXECUTED
        self.executed_at = at

    def mark_failed(self) -> None:
        self.status = JobStatus.FAILED
        self.attempts += 1
