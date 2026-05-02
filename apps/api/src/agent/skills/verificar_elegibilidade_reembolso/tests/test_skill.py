# apps/api/src/agent/skills/verificar_elegibilidade_reembolso/tests/test_skill.py
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.skills.verificar_elegibilidade_reembolso.skill import VerificarElegibilidadeReembolsoTool
from agent.skills.verificar_elegibilidade_reembolso.use_case import VerificarElegibilidadeReembolso


def _make_tool() -> VerificarElegibilidadeReembolsoTool:
    use_case = MagicMock(spec=VerificarElegibilidadeReembolso)
    return VerificarElegibilidadeReembolsoTool(use_case=use_case)


def test_tool_instantiation():
    tool = _make_tool()
    assert tool.name == "verificar_elegibilidade_reembolso"
    assert tool.description


def test_tool_has_correct_schema():
    tool = _make_tool()
    schema = tool.args_schema.model_json_schema()
    assert "email" in schema["properties"]
    assert "produto_id" in schema["properties"]


@pytest.mark.asyncio
async def test_arun_elegivel():
    use_case = AsyncMock(spec=VerificarElegibilidadeReembolso)
    use_case.execute.return_value = {
        "elegivel": True,
        "motivo": None,
        "dias_restantes": 5,
        "valor": 297.00,
    }
    tool = VerificarElegibilidadeReembolsoTool(use_case=use_case)
    fake_config = {"configurable": {"account_id": "acc1"}}
    with patch(
        "agent.skills.verificar_elegibilidade_reembolso.skill.get_config",
        return_value=fake_config,
    ):
        result = await tool._arun(email="joao@email.com", produto_id="prod-1")
    assert "elegível" in result
    assert "297" in result


@pytest.mark.asyncio
async def test_arun_inelegivel():
    use_case = AsyncMock(spec=VerificarElegibilidadeReembolso)
    use_case.execute.return_value = {
        "elegivel": False,
        "motivo": "Prazo de reembolso expirado.",
    }
    tool = VerificarElegibilidadeReembolsoTool(use_case=use_case)
    fake_config = {"configurable": {"account_id": "acc1"}}
    with patch(
        "agent.skills.verificar_elegibilidade_reembolso.skill.get_config",
        return_value=fake_config,
    ):
        result = await tool._arun(email="joao@email.com", produto_id="prod-1")
    assert "não elegível" in result
    assert "Prazo" in result
