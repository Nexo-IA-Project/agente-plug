# apps/api/src/agent/skills/buscar_conhecimento/tests/test_skill.py
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.skills.buscar_conhecimento.skill import BuscarConhecimentoTool
from agent.skills.buscar_conhecimento.use_case import BuscarConhecimento


def _make_tool() -> BuscarConhecimentoTool:
    use_case = MagicMock(spec=BuscarConhecimento)
    return BuscarConhecimentoTool(use_case=use_case)


def test_tool_instantiation():
    tool = _make_tool()
    assert tool.name == "buscar_conhecimento"
    assert tool.description


def test_tool_has_correct_schema():
    tool = _make_tool()
    schema = tool.args_schema.model_json_schema()
    assert "query" in schema["properties"]


@pytest.mark.asyncio
async def test_arun_encontrado():
    use_case = AsyncMock(spec=BuscarConhecimento)
    use_case.execute.return_value = {
        "encontrado": True,
        "chunks": ["O acesso ao curso é feito pelo link enviado por e-mail."],
        "strategy": "exact",
    }
    tool = BuscarConhecimentoTool(use_case=use_case)
    fake_config = {"configurable": {"account_id": "1"}}
    with patch("agent.skills.buscar_conhecimento.skill.get_config", return_value=fake_config):
        result = await tool._arun(query="como acessar o curso")
    assert "acesso ao curso" in result


@pytest.mark.asyncio
async def test_arun_nao_encontrado():
    use_case = AsyncMock(spec=BuscarConhecimento)
    use_case.execute.return_value = {
        "encontrado": False,
        "chunks": [],
        "strategy": "all_failed",
    }
    tool = BuscarConhecimentoTool(use_case=use_case)
    fake_config = {"configurable": {"account_id": "1"}}
    with patch("agent.skills.buscar_conhecimento.skill.get_config", return_value=fake_config):
        result = await tool._arun(query="topico desconhecido xyz")
    assert "Não encontrei" in result
