from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class KnowledgeChunk:
    id: str
    document_id: str
    account_id: int
    text: str
    chunk_index: int
    score: float


@runtime_checkable
class KnowledgePort(Protocol):
    async def search(
        self,
        query: str,
        account_id: int,
        threshold: float = 0.55,
        top_k: int = 5,
    ) -> list[KnowledgeChunk]: ...
