# tests/unit/use_cases/kb/test_buscar_chunks.py
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from nexoia.application.use_cases.kb.buscar_chunks import BuscarChunks
from nexoia.application.use_cases.kb.deletar_documento import DeletarDocumento
from nexoia.application.use_cases.kb.listar_documentos import ListarDocumentos

# ── BuscarChunks ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_buscar_chunks_returns_results():
    chunk_repo = AsyncMock()
    embeddings = AsyncMock()
    usage_repo = AsyncMock()

    embeddings.embed = AsyncMock(return_value=[0.1, 0.2, 0.3])
    chunk_repo.similarity_search = AsyncMock(return_value=[
        {"chunk_id": "c1", "text": "answer text", "score": 0.85}
    ])

    uc = BuscarChunks(chunk_repo=chunk_repo, embeddings=embeddings, usage_repo=usage_repo)
    results = await uc.execute(account_id=1, query="my question", top_k=5, threshold=0.5)

    assert len(results) == 1
    assert results[0]["text"] == "answer text"
    embeddings.embed.assert_awaited_once_with("my question")
    chunk_repo.similarity_search.assert_awaited_once()


@pytest.mark.asyncio
async def test_buscar_chunks_logs_when_no_results():
    chunk_repo = AsyncMock()
    embeddings = AsyncMock()
    usage_repo = AsyncMock()

    embeddings.embed = AsyncMock(return_value=[0.1, 0.2])
    chunk_repo.similarity_search = AsyncMock(return_value=[])

    uc = BuscarChunks(chunk_repo=chunk_repo, embeddings=embeddings, usage_repo=usage_repo)
    results = await uc.execute(account_id=1, query="no results query", top_k=5, threshold=0.8)

    assert results == []
    usage_repo.record_no_result.assert_awaited_once_with(
        account_id=1, query="no results query"
    )


# ── ListarDocumentos ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_listar_documentos_delegates_to_repo():
    doc_repo = AsyncMock()
    doc_repo.list_by_account = AsyncMock(return_value=[])
    uc = ListarDocumentos(doc_repo)
    result = await uc.execute(account_id=1, offset=0, limit=10)
    assert result == []
    doc_repo.list_by_account.assert_awaited_once_with(1, offset=0, limit=10)


# ── DeletarDocumento ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_deletar_documento_deletes_chunks_then_document():
    doc_repo = AsyncMock()
    chunk_repo = AsyncMock()
    uc = DeletarDocumento(doc_repo=doc_repo, chunk_repo=chunk_repo)
    await uc.execute(doc_id="doc-1", account_id=1)

    chunk_repo.delete_by_document.assert_awaited_once_with("doc-1")
    doc_repo.delete.assert_awaited_once_with("doc-1", account_id=1)
