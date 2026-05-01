# apps/api/src/agent/skills/oferecer_retencao/tests/test_skill.py
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agent.skills.oferecer_retencao.skill import OfereceRetencaoTool
from agent.skills.oferecer_retencao.use_case import OfereceRetencao


def _make_tool() -> OfereceRetencaoTool:
    use_case = MagicMock(spec=OfereceRetencao)
    return OfereceRetencaoTool(use_case=use_case)


def test_tool_instantiation():
    tool = _make_tool()
    assert tool.name == "oferecer_retencao"
    assert tool.description


def test_tool_has_correct_schema():
    tool = _make_tool()
    schema = tool.args_schema.model_json_schema()
    assert "email" in schema["properties"]
    assert "produto_id" in schema["properties"]


@pytest.mark.asyncio
async def test_arun_tem_oferta():
    use_case = AsyncMock(spec=OfereceRetencao)
    use_case.execute.return_value = {
        "tem_oferta": True,
        "descricao": "Pausa de 30 dias na assinatura",
        "tipo": "pausa",
        "valor_desconto": 0.0,
    }
    tool = OfereceRetencaoTool(use_case=use_case)
    fake_config = {"configurable": {"account_id": "acc1"}}
    with patch("agent.skills.oferecer_retencao.skill.get_config", return_value=fake_config):
        result = await tool._arun(email="joao@email.com", produto_id="prod-1")
    assert "Pausa de 30 dias" in result
    assert "pausa" in result


@pytest.mark.asyncio
async def test_arun_sem_oferta():
    use_case = AsyncMock(spec=OfereceRetencao)
    use_case.execute.return_value = {"tem_oferta": False}
    tool = OfereceRetencaoTool(use_case=use_case)
    fake_config = {"configurable": {"account_id": "acc1"}}
    with patch("agent.skills.oferecer_retencao.skill.get_config", return_value=fake_config):
        result = await tool._arun(email="joao@email.com", produto_id="prod-1")
    assert "Nenhuma oferta" in result
