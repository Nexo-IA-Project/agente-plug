# apps/api/src/agent/skills/processar_reembolso/tests/test_skill.py
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.skills.processar_reembolso.skill import ProcessarReembolsoTool
from agent.skills.processar_reembolso.use_case import ProcessarReembolso


def _make_tool() -> ProcessarReembolsoTool:
    use_case = MagicMock(spec=ProcessarReembolso)
    return ProcessarReembolsoTool(use_case=use_case)


def test_tool_instantiation():
    tool = _make_tool()
    assert tool.name == "processar_reembolso"
    assert tool.description


def test_tool_has_correct_schema():
    tool = _make_tool()
    schema = tool.args_schema.model_json_schema()
    assert "email" in schema["properties"]
    assert "produto_id" in schema["properties"]


@pytest.mark.asyncio
async def test_arun_reembolso_processado():
    use_case = AsyncMock(spec=ProcessarReembolso)
    use_case.execute.return_value = {
        "processado": True,
        "protocolo": "RMB-20260430-001",
        "valor": 297.00,
        "prazo_estorno": "5 a 10 dias úteis",
    }
    tool = ProcessarReembolsoTool(use_case=use_case)
    fake_config = {"configurable": {"account_id": "acc1"}}
    with patch("agent.skills.processar_reembolso.skill.get_config", return_value=fake_config):
        result = await tool._arun(email="joao@email.com", produto_id="prod-1")
    assert "RMB-20260430-001" in result
    assert "297" in result


@pytest.mark.asyncio
async def test_arun_reembolso_falhou():
    use_case = AsyncMock(spec=ProcessarReembolso)
    use_case.execute.return_value = {
        "processado": False,
        "motivo": "Erro na plataforma Hubla.",
    }
    tool = ProcessarReembolsoTool(use_case=use_case)
    fake_config = {"configurable": {"account_id": "acc1"}}
    with patch("agent.skills.processar_reembolso.skill.get_config", return_value=fake_config):
        result = await tool._arun(email="joao@email.com", produto_id="prod-1")
    assert "não processado" in result
    assert "Hubla" in result
