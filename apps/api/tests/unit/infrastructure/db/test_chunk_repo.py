# tests/unit/infrastructure/db/test_chunk_repo.py
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from shared.domain.entities.knowledge_chunk import KnowledgeChunk
from shared.adapters.db.repositories.chunk_repo import ChunkRepository


def _make_chunk(index: int = 0) -> KnowledgeChunk:
    return KnowledgeChunk(
        document_id="doc-1",
        account_id=1,
        text=f"chunk text {index}",
        chunk_index=index,
        token_count=3,
        embedding=[0.1, 0.2, 0.3],
    )


@pytest.mark.asyncio
async def test_save_batch_adds_all_models():
    session = AsyncMock()
    session.add = MagicMock()  # synchronous in AsyncSession
    repo = ChunkRepository(session)
    chunks = [_make_chunk(0), _make_chunk(1), _make_chunk(2)]
    await repo.save_batch(chunks)
    assert session.add.call_count == 3
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_save_batch_empty_list_does_not_flush():
    session = AsyncMock()
    session.add = MagicMock()
    repo = ChunkRepository(session)
    await repo.save_batch([])
    session.add.assert_not_called()
    session.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_by_document_executes_delete():
    session = AsyncMock()
    repo = ChunkRepository(session)
    await repo.delete_by_document("doc-1")
    session.execute.assert_awaited_once()
    session.flush.assert_awaited_once()
