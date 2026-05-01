# apps/api/src/agent/skills/buscar_aluno_cademi/tests/test_skill.py
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agent.skills.buscar_aluno_cademi.skill import BuscarAlunoCademiTool
from agent.skills.buscar_aluno_cademi.use_case import BuscarAlunoCademi


def _make_tool() -> BuscarAlunoCademiTool:
    use_case = MagicMock(spec=BuscarAlunoCademi)
    return BuscarAlunoCademiTool(use_case=use_case)


def test_tool_instantiation():
    tool = _make_tool()
    assert tool.name == "buscar_aluno_cademi"
    assert tool.description  # loaded from instructions.md


def test_tool_has_correct_schema():
    tool = _make_tool()
    schema = tool.args_schema.model_json_schema()
    assert "phone" in schema["properties"]


@pytest.mark.asyncio
async def test_arun_returns_aluno_data():
    use_case = AsyncMock(spec=BuscarAlunoCademi)
    use_case.execute.return_value = {
        "encontrado": True,
        "nome": "João Silva",
        "email": "joao@email.com",
        "cursos": ["Curso A"],
    }
    tool = BuscarAlunoCademiTool(use_case=use_case)
    fake_config = {"configurable": {"account_id": "acc1", "phone": "5511999998888"}}
    with patch("agent.skills.buscar_aluno_cademi.skill.get_config", return_value=fake_config):
        result = await tool._arun(phone="5511999998888")
    assert "João Silva" in result
    assert "joao@email.com" in result


@pytest.mark.asyncio
async def test_arun_returns_not_found_message():
    use_case = AsyncMock(spec=BuscarAlunoCademi)
    use_case.execute.return_value = {
        "encontrado": False,
        "mensagem": "Aluno não encontrado na base Cademi.",
    }
    tool = BuscarAlunoCademiTool(use_case=use_case)
    fake_config = {"configurable": {"account_id": "acc1", "phone": "5511000000000"}}
    with patch("agent.skills.buscar_aluno_cademi.skill.get_config", return_value=fake_config):
        result = await tool._arun(phone="5511000000000")
    assert "não encontrado" in result
