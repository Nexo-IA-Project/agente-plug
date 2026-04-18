from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class IntegrationType(StrEnum):
    HUBLA = "hubla"
    CADEMI = "cademi"
    META = "meta"
    CHATNEXO = "chatnexo"


@dataclass(slots=True)
class IntegrationConfig:
    id: UUID
    account_id: UUID
    integration_type: IntegrationType
    credentials_encrypted: bytes
    enabled: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None
