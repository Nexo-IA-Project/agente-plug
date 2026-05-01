from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from agent.skills.core import make_core_skills, EscalarParaHumanoTool


def test_make_core_skills_returns_one_tool():
    tools = make_core_skills(chatnexo=AsyncMock())
    assert len(tools) == 1
    assert tools[0].name == "escalar_para_humano"


@pytest.mark.asyncio
async def test_escalar_para_humano_tool_calls_chatnexo():
    chatnexo = AsyncMock()
    tool = EscalarParaHumanoTool(chatnexo=chatnexo)
    fake_cfg = {"configurable": {"account_id": "t1", "phone": "5511999", "conversation_id": "c1"}}
    with patch("agent.skills.core.get_config", return_value=fake_cfg):
        result = await tool._arun(reason="legal_mention")
    chatnexo.transfer_to_human.assert_called_once_with(
        account_id="t1",
        conversation_id="c1",
        reason="legal_mention",
    )
    assert "TRANSFERIDO" in result
    assert "legal_mention" in result


@pytest.mark.asyncio
async def test_escalar_para_humano_tool_default_reason():
    chatnexo = AsyncMock()
    tool = EscalarParaHumanoTool(chatnexo=chatnexo)
    fake_cfg = {"configurable": {"account_id": "t1", "phone": "5511999", "conversation_id": "c1"}}
    with patch("agent.skills.core.get_config", return_value=fake_cfg):
        result = await tool._arun()
    chatnexo.transfer_to_human.assert_called_once_with(
        account_id="t1",
        conversation_id="c1",
        reason="solicitado_pelo_usuario",
    )
    assert "TRANSFERIDO" in result
