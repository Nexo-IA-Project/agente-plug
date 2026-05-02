# tests/unit/infrastructure/db/test_document_repo.py
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from shared.adapters.db.repositories.document_repo import DocumentRepository
from shared.domain.entities.knowledge_document import DocumentStatus, KnowledgeDocument


def _make_doc(**kwargs) -> KnowledgeDocument:
    defaults = {
        "account_id": 1,
        "filename": "test.pdf",
        "mime_type": "application/pdf",
        "file_size_bytes": 1024,
        "created_by": "admin@test.com",
    }
    defaults.update(kwargs)
    return KnowledgeDocument(**defaults)


@pytest.mark.asyncio
async def test_save_adds_and_flushes():
    session = AsyncMock()
    session.add = MagicMock()  # add() is synchronous in SQLAlchemy AsyncSession
    repo = DocumentRepository(session)
    doc = _make_doc()
    await repo.save(doc)
    session.add.assert_called_once()
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_returns_none_when_not_found():
    session = AsyncMock()
    session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    )
    repo = DocumentRepository(session)
    result = await repo.get("nonexistent-id", account_id=1)
    assert result is None


@pytest.mark.asyncio
async def test_get_returns_entity_when_found():
    session = AsyncMock()
    from shared.adapters.db.models import KnowledgeDocumentModel

    model = KnowledgeDocumentModel(
        id="doc-1",
        account_id=1,
        filename="test.pdf",
        mime_type="application/pdf",
        file_size_bytes=1024,
        status="pending",
        chunk_count=0,
        tags=[],
        error_message=None,
        created_by="admin@test.com",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=model))
    )
    repo = DocumentRepository(session)
    result = await repo.get("doc-1", account_id=1)
    assert result is not None
    assert result.id == "doc-1"
    assert result.filename == "test.pdf"
    assert result.status == DocumentStatus.PENDING


@pytest.mark.asyncio
async def test_update_status_flushes():
    session = AsyncMock()
    from shared.adapters.db.models import KnowledgeDocumentModel

    model = KnowledgeDocumentModel(
        id="doc-1",
        account_id=1,
        filename="f.pdf",
        mime_type="application/pdf",
        file_size_bytes=0,
        status="pending",
        chunk_count=0,
        tags=[],
        error_message=None,
        created_by="a",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.get = AsyncMock(return_value=model)
    repo = DocumentRepository(session)
    await repo.update_status("doc-1", DocumentStatus.INDEXED)
    assert model.status == "indexed"
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_status_with_error_message():
    session = AsyncMock()
    from shared.adapters.db.models import KnowledgeDocumentModel

    model = KnowledgeDocumentModel(
        id="doc-1",
        account_id=1,
        filename="f.pdf",
        mime_type="application/pdf",
        file_size_bytes=0,
        status="processing",
        chunk_count=0,
        tags=[],
        error_message=None,
        created_by="a",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.get = AsyncMock(return_value=model)
    repo = DocumentRepository(session)
    await repo.update_status("doc-1", DocumentStatus.ERROR, error="extraction failed")
    assert model.status == "error"
    assert model.error_message == "extraction failed"


@pytest.mark.asyncio
async def test_delete_executes_delete():
    session = AsyncMock()
    repo = DocumentRepository(session)
    await repo.delete("doc-1", account_id=1)
    session.execute.assert_awaited_once()
    session.flush.assert_awaited_once()
