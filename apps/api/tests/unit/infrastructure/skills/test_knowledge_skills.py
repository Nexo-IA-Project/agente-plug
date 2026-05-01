from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agent.skills.knowledge import (
    make_knowledge_skills,
    BuscarConhecimentoTool,
    BuscarConhecimentoComContextoTool,
)


def test_make_knowledge_skills_returns_two_tools():
    skills = make_knowledge_skills(
        knowledge_repo=AsyncMock(),
        usage_log_repo=AsyncMock(),
        chatnexo=AsyncMock(),
    )
    assert len(skills) == 2


def test_make_knowledge_skills_tool_names():
    skills = make_knowledge_skills(
        knowledge_repo=AsyncMock(),
        usage_log_repo=AsyncMock(),
        chatnexo=AsyncMock(),
    )
    names = {s.name for s in skills}
    assert names == {"buscar_conhecimento", "buscar_conhecimento_com_contexto"}


@pytest.mark.asyncio
async def test_buscar_conhecimento_tool_returns_chunks_when_found():
    buscar_uc = AsyncMock()
    chunk = MagicMock()
    chunk.text = "Resposta aqui."
    result_obj = MagicMock()
    result_obj.status = "found"
    result_obj.chunks = [chunk]
    buscar_uc.execute.return_value = result_obj
    tool = BuscarConhecimentoTool(buscar_uc=buscar_uc)
    fake_cfg = {"configurable": {"account_id": "t1", "phone": "5511999"}}
    with patch("agent.skills.knowledge.get_config", return_value=fake_cfg):
        result = await tool._arun(query="como acesso o curso?")
    assert result == "Resposta aqui."


@pytest.mark.asyncio
async def test_buscar_conhecimento_tool_returns_ask_context_when_not_found():
    buscar_uc = AsyncMock()
    result_obj = MagicMock()
    result_obj.status = "ask_context"
    result_obj.chunks = []
    buscar_uc.execute.return_value = result_obj
    tool = BuscarConhecimentoTool(buscar_uc=buscar_uc)
    fake_cfg = {"configurable": {"account_id": "t1", "phone": "5511999"}}
    with patch("agent.skills.knowledge.get_config", return_value=fake_cfg):
        result = await tool._arun(query="algo vago")
    assert result.startswith("ASK_CONTEXT:")


@pytest.mark.asyncio
async def test_buscar_conhecimento_com_contexto_tool_calls_use_case():
    contexto_uc = AsyncMock()
    result_obj = MagicMock()
    result_obj.status = "escalated"
    result_obj.chunks = []
    contexto_uc.execute.return_value = result_obj
    tool = BuscarConhecimentoComContextoTool(contexto_uc=contexto_uc)
    fake_cfg = {"configurable": {"account_id": "t1", "phone": "5511999", "conversation_id": "c1"}}
    with patch("agent.skills.knowledge.get_config", return_value=fake_cfg):
        result = await tool._arun(original_query="pergunta", context="contexto adicional")
    contexto_uc.execute.assert_called_once_with(
        original_query="pergunta",
        context="contexto adicional",
        account_id="t1",
        conversation_id="c1",
    )
    assert "ESCALATED" in result
