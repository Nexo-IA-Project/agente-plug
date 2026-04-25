# tests/unit/use_cases/knowledge/test_buscar_conhecimento_com_contexto.py
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nexoia.application.use_cases.knowledge.buscar_conhecimento_com_contexto import (
    BuscarConhecimentoComContexto,
)
from nexoia.domain.ports.knowledge import KnowledgeChunk


def _make_chunk(text: str = "resposta encontrada") -> KnowledgeChunk:
    return KnowledgeChunk(
        id="chunk-2",
        document_id="doc-2",
        account_id=1,
        text=text,
        chunk_index=0,
        score=0.82,
    )


def _make_settings(threshold: float = 0.55, top_k: int = 5) -> MagicMock:
    s = MagicMock()
    s.kb_attempt_1_threshold = threshold
    s.kb_top_k = top_k
    return s


@pytest.mark.asyncio
async def test_found_with_context_returns_found_status():
    """Busca com contexto enriquecido retorna chunks → status 'found'."""
    repo = AsyncMock()
    repo.search = AsyncMock(return_value=[_make_chunk()])
    usage_log = AsyncMock()
    chatnexo = AsyncMock()
    uc = BuscarConhecimentoComContexto(repo, usage_log, chatnexo)

    with patch(
        "nexoia.application.use_cases.knowledge.buscar_conhecimento_com_contexto.get_settings",
        return_value=_make_settings(),
    ):
        result = await uc.execute(
            original_query="como acessar",
            context="minha conta está bloqueada",
            account_id=1,
            conversation_id="conv-123",
        )

    assert result.status == "found"
    assert len(result.chunks) == 1
    call_query = repo.search.call_args[0][0]
    assert "como acessar" in call_query
    assert "minha conta está bloqueada" in call_query
    chatnexo.transfer_to_human.assert_not_called()
    usage_log.record_no_result.assert_not_called()


@pytest.mark.asyncio
async def test_escalates_when_context_search_fails():
    """Busca com contexto falha → registra no log + escalada para humano → status 'escalated'."""
    repo = AsyncMock()
    repo.search = AsyncMock(return_value=[])
    usage_log = AsyncMock()
    chatnexo = AsyncMock()
    uc = BuscarConhecimentoComContexto(repo, usage_log, chatnexo)

    with patch(
        "nexoia.application.use_cases.knowledge.buscar_conhecimento_com_contexto.get_settings",
        return_value=_make_settings(),
    ):
        result = await uc.execute(
            original_query="problema xpto",
            context="detalhes irrelevantes",
            account_id=1,
            conversation_id="conv-456",
        )

    assert result.status == "escalated"
    assert result.chunks == []
    usage_log.record_no_result.assert_called_once_with(1, "problema xpto")
    chatnexo.transfer_to_human.assert_called_once_with(
        account_id="1",
        conversation_id="conv-456",
        reason="knowledge_not_found",
    )


@pytest.mark.asyncio
async def test_search_uses_enriched_query():
    """Query enriquecida é formada por original_query + ' ' + context."""
    repo = AsyncMock()
    repo.search = AsyncMock(return_value=[_make_chunk()])
    usage_log = AsyncMock()
    chatnexo = AsyncMock()
    uc = BuscarConhecimentoComContexto(repo, usage_log, chatnexo)

    with patch(
        "nexoia.application.use_cases.knowledge.buscar_conhecimento_com_contexto.get_settings",
        return_value=_make_settings(),
    ):
        await uc.execute(
            original_query="certificado",
            context="não aparece no perfil",
            account_id=2,
            conversation_id="conv-789",
        )

    enriched = repo.search.call_args[0][0]
    assert enriched == "certificado não aparece no perfil"
    assert repo.search.call_args[0][1] == 2
