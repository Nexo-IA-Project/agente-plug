from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(slots=True)
class AuditEvent:
    id: UUID
    account_id: UUID
    actor: str
    user_id: str | None
    user_name: str | None
    action: str
    resource_type: str
    resource_id: str | None
    ip_address: str | None
    geo_city: str | None
    geo_country: str | None
    geo_region: str | None
    metadata: dict[str, Any] = field(default_factory=dict)
    correlation_id: str | None = None
    created_at: datetime | None = None
