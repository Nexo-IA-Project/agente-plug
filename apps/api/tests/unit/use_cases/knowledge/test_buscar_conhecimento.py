# tests/unit/use_cases/knowledge/test_buscar_conhecimento.py
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shared.application.use_cases.knowledge.buscar_conhecimento import BuscarConhecimento
from shared.application.use_cases.knowledge.keyword_extractor import KeywordExtractor
from shared.application.use_cases.knowledge.synonym_expander import SynonymExpander
from shared.domain.ports.knowledge import KnowledgeChunk


def _make_chunk(text: str = "conteúdo relevante") -> KnowledgeChunk:
    return KnowledgeChunk(
        id="chunk-1",
        document_id="doc-1",
        account_id=1,
        text=text,
        chunk_index=0,
        score=0.87,
    )


def _make_settings(threshold: float = 0.55, top_k: int = 5) -> MagicMock:
    s = MagicMock()
    s.kb_attempt_1_threshold = threshold
    s.kb_top_k = top_k
    return s


@pytest.mark.asyncio
async def test_found_on_first_attempt():
    """Busca exata retorna chunks na 1ª tentativa → status 'found'."""
    repo = AsyncMock()
    repo.search = AsyncMock(return_value=[_make_chunk()])
    uc = BuscarConhecimento(repo, SynonymExpander(), KeywordExtractor())

    with patch(
        "nexoia.application.use_cases.knowledge.buscar_conhecimento.get_settings",
        return_value=_make_settings(),
    ):
        result = await uc.execute(query="como acessar", account_id=1)

    assert result.status == "found"
    assert len(result.chunks) == 1
    assert repo.search.call_count == 1


@pytest.mark.asyncio
async def test_found_on_second_attempt_synonyms():
    """1ª tentativa falha, 2ª com sinônimos retorna chunks → status 'found'."""
    repo = AsyncMock()
    repo.search = AsyncMock(side_effect=[[], [_make_chunk()]])
    uc = BuscarConhecimento(repo, SynonymExpander(), KeywordExtractor())

    with patch(
        "nexoia.application.use_cases.knowledge.buscar_conhecimento.get_settings",
        return_value=_make_settings(),
    ):
        result = await uc.execute(query="como acessar", account_id=1)

    assert result.status == "found"
    assert repo.search.call_count == 2
    second_call_query = repo.search.call_args_list[1][0][0]
    assert "entrar" in second_call_query or "logar" in second_call_query


@pytest.mark.asyncio
async def test_found_on_third_attempt_keywords():
    """1ª e 2ª falham, 3ª com keywords retorna chunks → status 'found'."""
    repo = AsyncMock()
    repo.search = AsyncMock(side_effect=[[], [], [_make_chunk()]])
    uc = BuscarConhecimento(repo, SynonymExpander(), KeywordExtractor())

    with patch(
        "nexoia.application.use_cases.knowledge.buscar_conhecimento.get_settings",
        return_value=_make_settings(),
    ):
        result = await uc.execute(query="como acessar o curso", account_id=1)

    assert result.status == "found"
    assert repo.search.call_count == 3


@pytest.mark.asyncio
async def test_ask_context_when_all_attempts_fail():
    """Todas as 3 tentativas falham → status 'ask_context', chunks vazio."""
    repo = AsyncMock()
    repo.search = AsyncMock(return_value=[])
    uc = BuscarConhecimento(repo, SynonymExpander(), KeywordExtractor())

    with patch(
        "nexoia.application.use_cases.knowledge.buscar_conhecimento.get_settings",
        return_value=_make_settings(),
    ):
        result = await uc.execute(query="xpto zzzz", account_id=1)

    assert result.status == "ask_context"
    assert result.chunks == []
