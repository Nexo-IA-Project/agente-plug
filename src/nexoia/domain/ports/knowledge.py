from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable
from uuid import UUID


@dataclass(frozen=True, slots=True)
class KnowledgeHit:
    document_id: UUID
    chunk_text: str
    score: float


@runtime_checkable
class KnowledgePort(Protocol):
    async def search(
        self, *, account_id: UUID, query: str, top_k: int = 5
    ) -> list[KnowledgeHit]: ...
