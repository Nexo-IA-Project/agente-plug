# tests/unit/use_cases/kb/test_ingerir_documento.py
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from nexoia.application.use_cases.kb.ingerir_documento import IngerirDocumento
from nexoia.domain.entities.knowledge_document import DocumentStatus, KnowledgeDocument


def _make_document(doc_id: str = "doc-1") -> KnowledgeDocument:
    return KnowledgeDocument(
        id=doc_id,
        account_id=1,
        filename="manual.pdf",
        mime_type="text/plain",
        file_size_bytes=100,
        created_by="admin@test.com",
    )


def _make_use_case():
    doc_repo = AsyncMock()
    chunk_repo = AsyncMock()
    extractor = MagicMock()
    chunker = MagicMock()
    embeddings = AsyncMock()
    return IngerirDocumento(doc_repo, chunk_repo, extractor, chunker, embeddings), {
        "doc_repo": doc_repo,
        "chunk_repo": chunk_repo,
        "extractor": extractor,
        "chunker": chunker,
        "embeddings": embeddings,
    }


@pytest.mark.asyncio
async def test_happy_path_indexes_document():
    uc, deps = _make_use_case()
    doc = _make_document("doc-1")
    deps["doc_repo"].get = AsyncMock(return_value=doc)
    deps["extractor"].extract = MagicMock(return_value="chunk text content")
    deps["chunker"].chunk = MagicMock(return_value=["chunk text content"])
    deps["embeddings"].embed_batch = AsyncMock(return_value=[[0.1, 0.2, 0.3]])

    await uc.execute(doc_id="doc-1", content=b"raw bytes", account_id=1)

    # Must set PROCESSING then INDEXED
    calls = [call.args for call in deps["doc_repo"].update_status.call_args_list]
    statuses = [c[1] for c in calls]  # second arg is status
    assert DocumentStatus.PROCESSING in statuses
    assert DocumentStatus.INDEXED in statuses

    # Must save chunks
    deps["chunk_repo"].save_batch.assert_awaited_once()

    # Must update chunk count
    deps["doc_repo"].update_chunk_count.assert_awaited_once_with("doc-1", 1)


@pytest.mark.asyncio
async def test_sets_processing_before_indexing():
    uc, deps = _make_use_case()
    doc = _make_document("doc-2")
    deps["doc_repo"].get = AsyncMock(return_value=doc)
    deps["extractor"].extract = MagicMock(return_value="text")
    deps["chunker"].chunk = MagicMock(return_value=["text"])
    deps["embeddings"].embed_batch = AsyncMock(return_value=[[0.1]])

    await uc.execute(doc_id="doc-2", content=b"data", account_id=1)

    first_call = deps["doc_repo"].update_status.call_args_list[0]
    assert first_call.args[1] == DocumentStatus.PROCESSING


@pytest.mark.asyncio
async def test_on_extraction_error_sets_error_status():
    uc, deps = _make_use_case()
    doc = _make_document("doc-3")
    deps["doc_repo"].get = AsyncMock(return_value=doc)
    deps["extractor"].extract = MagicMock(side_effect=ValueError("corrupt PDF"))

    with pytest.raises(ValueError, match="corrupt PDF"):
        await uc.execute(doc_id="doc-3", content=b"bad", account_id=1)

    # Last update_status call must be ERROR
    last_call = deps["doc_repo"].update_status.call_args_list[-1]
    assert last_call.args[1] == DocumentStatus.ERROR
    assert "corrupt PDF" in last_call.args[2]  # error message


@pytest.mark.asyncio
async def test_idempotency_deletes_old_chunks_before_save():
    uc, deps = _make_use_case()
    doc = _make_document("doc-4")
    deps["doc_repo"].get = AsyncMock(return_value=doc)
    deps["extractor"].extract = MagicMock(return_value="text")
    deps["chunker"].chunk = MagicMock(return_value=["text"])
    deps["embeddings"].embed_batch = AsyncMock(return_value=[[0.1]])

    await uc.execute(doc_id="doc-4", content=b"data", account_id=1)

    # delete_by_document must be called before save_batch
    delete_order = deps["chunk_repo"].delete_by_document.call_args_list
    save_order = deps["chunk_repo"].save_batch.call_args_list
    assert len(delete_order) == 1
    assert len(save_order) == 1
    deps["chunk_repo"].delete_by_document.assert_awaited_once_with("doc-4")
