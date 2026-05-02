# apps/api/src/agent/skills/verificar_caso_acesso/tests/test_skill.py
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.skills.verificar_caso_acesso.skill import VerificarCasoAcessoTool
from agent.skills.verificar_caso_acesso.use_case import VerificarCasoAcesso


def _make_tool() -> VerificarCasoAcessoTool:
    use_case = MagicMock(spec=VerificarCasoAcesso)
    return VerificarCasoAcessoTool(use_case=use_case)


def test_tool_instantiation():
    tool = _make_tool()
    assert tool.name == "verificar_caso_acesso"
    assert tool.description


def test_tool_has_correct_schema():
    tool = _make_tool()
    schema = tool.args_schema.model_json_schema()
    assert "email" in schema["properties"]


@pytest.mark.asyncio
async def test_arun_returns_caso_encontrado():
    use_case = AsyncMock(spec=VerificarCasoAcesso)
    use_case.execute.return_value = {
        "tem_caso": True,
        "status": "aberto",
        "caso_id": "caso-123",
    }
    tool = VerificarCasoAcessoTool(use_case=use_case)
    fake_config = {"configurable": {"account_id": "acc1"}}
    with patch("agent.skills.verificar_caso_acesso.skill.get_config", return_value=fake_config):
        result = await tool._arun(email="joao@email.com")
    assert "aberto" in result
    assert "caso-123" in result


@pytest.mark.asyncio
async def test_arun_returns_nenhum_caso():
    use_case = AsyncMock(spec=VerificarCasoAcesso)
    use_case.execute.return_value = {
        "tem_caso": False,
        "status": "inexistente",
        "caso_id": None,
    }
    tool = VerificarCasoAcessoTool(use_case=use_case)
    fake_config = {"configurable": {"account_id": "acc1"}}
    with patch("agent.skills.verificar_caso_acesso.skill.get_config", return_value=fake_config):
        result = await tool._arun(email="inexistente@email.com")
    assert "Nenhum caso" in result
