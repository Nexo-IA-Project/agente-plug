# apps/api/src/agent/skills/buscar_conhecimento_com_contexto/tests/test_skill.py
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agent.skills.buscar_conhecimento_com_contexto.skill import BuscarConhecimentoComContextoTool
from agent.skills.buscar_conhecimento_com_contexto.use_case import BuscarConhecimentoComContexto


def _make_tool() -> BuscarConhecimentoComContextoTool:
    use_case = MagicMock(spec=BuscarConhecimentoComContexto)
    return BuscarConhecimentoComContextoTool(use_case=use_case)


def test_tool_instantiation():
    tool = _make_tool()
    assert tool.name == "buscar_conhecimento_com_contexto"
    assert tool.description


def test_tool_has_correct_schema():
    tool = _make_tool()
    schema = tool.args_schema.model_json_schema()
    assert "query" in schema["properties"]
    assert "contexto_aluno" in schema["properties"]


@pytest.mark.asyncio
async def test_arun_encontrado_com_contexto():
    use_case = AsyncMock(spec=BuscarConhecimentoComContexto)
    use_case.execute.return_value = {
        "encontrado": True,
        "chunks": ["Alunos do Curso A acessam via app mobile."],
        "strategy": "context_enriched",
        "escalar": False,
    }
    tool = BuscarConhecimentoComContextoTool(use_case=use_case)
    fake_config = {"configurable": {"account_id": "1"}}
    with patch(
        "agent.skills.buscar_conhecimento_com_contexto.skill.get_config",
        return_value=fake_config,
    ):
        result = await tool._arun(query="como acessar", contexto_aluno="Curso A")
    assert "app mobile" in result


@pytest.mark.asyncio
async def test_arun_nao_encontrado_escalar():
    use_case = AsyncMock(spec=BuscarConhecimentoComContexto)
    use_case.execute.return_value = {
        "encontrado": False,
        "chunks": [],
        "strategy": "context_failed",
        "escalar": True,
    }
    tool = BuscarConhecimentoComContextoTool(use_case=use_case)
    fake_config = {"configurable": {"account_id": "1"}}
    with patch(
        "agent.skills.buscar_conhecimento_com_contexto.skill.get_config",
        return_value=fake_config,
    ):
        result = await tool._arun(query="topico obscuro", contexto_aluno="Curso B")
    assert "escalar" in result.lower()
