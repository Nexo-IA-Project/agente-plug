# apps/api/src/agent/skills/escalar_para_humano/tests/test_skill.py
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agent.skills.escalar_para_humano.skill import EscalarParaHumanoTool
from shared.domain.ports.chatnexo import ChatNexoPort


def _make_tool() -> EscalarParaHumanoTool:
    chatnexo = MagicMock(spec=ChatNexoPort)
    return EscalarParaHumanoTool(chatnexo=chatnexo)


def test_tool_instantiation():
    tool = _make_tool()
    assert tool.name == "escalar_para_humano"
    assert tool.description


def test_tool_has_reason_schema():
    tool = _make_tool()
    schema = tool.args_schema.model_json_schema()
    # reason param exists with default value
    assert "reason" in schema.get("properties", {}) or not schema.get("required")


@pytest.mark.asyncio
async def test_arun_escala_e_retorna_confirmacao():
    chatnexo = AsyncMock(spec=ChatNexoPort)
    tool = EscalarParaHumanoTool(chatnexo=chatnexo)
    fake_config = {
        "configurable": {
            "account_id": "acc1",
            "phone": "5511999998888",
            "conversation_id": "conv-123",
        }
    }
    with patch("agent.skills.escalar_para_humano.skill.get_config", return_value=fake_config):
        result = await tool._arun(reason="solicitado_pelo_usuario")
    chatnexo.transfer_to_human.assert_called_once_with(
        account_id="acc1", conversation_id="conv-123", reason="solicitado_pelo_usuario"
    )
    assert "TRANSFERIDO" in result


@pytest.mark.asyncio
async def test_arun_chatnexo_recebe_parametros_corretos():
    chatnexo = AsyncMock(spec=ChatNexoPort)
    tool = EscalarParaHumanoTool(chatnexo=chatnexo)
    fake_config = {
        "configurable": {
            "account_id": "tenant-42",
            "phone": "5521988887777",
            "conversation_id": "c-abc",
        }
    }
    with patch("agent.skills.escalar_para_humano.skill.get_config", return_value=fake_config):
        await tool._arun(reason="legal_mention")
    call_kwargs = chatnexo.transfer_to_human.call_args.kwargs
    assert call_kwargs["account_id"] == "tenant-42"
    assert call_kwargs["reason"] == "legal_mention"
