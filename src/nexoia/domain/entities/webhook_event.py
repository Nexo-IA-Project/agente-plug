from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID


class WebhookSource(StrEnum):
    HUBLA = "hubla"
    CHATNEXO = "chatnexo"


class WebhookStatus(StrEnum):
    PENDING = "pending"
    PROCESSED = "processed"
    FAILED = "failed"


@dataclass(slots=True)
class WebhookEvent:
    id: UUID
    source: WebhookSource
    external_id: str
    payload: dict[str, Any]
    status: WebhookStatus
    correlation_id: str | None = None
    created_at: datetime | None = None
    processed_at: datetime | None = None
