from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4


@dataclass
class KnowledgeChunk:
    document_id: str
    account_id: UUID
    text: str
    chunk_index: int
    token_count: int
    embedding: list[float]
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
