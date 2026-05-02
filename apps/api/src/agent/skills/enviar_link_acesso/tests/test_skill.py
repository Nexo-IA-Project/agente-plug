# apps/api/src/agent/skills/enviar_link_acesso/tests/test_skill.py
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.skills.enviar_link_acesso.skill import EnviarLinkAcessoTool
from agent.skills.enviar_link_acesso.use_case import EnviarLinkAcesso


def _make_tool() -> EnviarLinkAcessoTool:
    use_case = MagicMock(spec=EnviarLinkAcesso)
    return EnviarLinkAcessoTool(use_case=use_case)


def test_tool_instantiation():
    tool = _make_tool()
    assert tool.name == "enviar_link_acesso"
    assert tool.description


def test_tool_has_correct_schema():
    tool = _make_tool()
    schema = tool.args_schema.model_json_schema()
    assert "email" in schema["properties"]
    assert "phone" in schema["properties"]


@pytest.mark.asyncio
async def test_arun_link_enviado():
    use_case = AsyncMock(spec=EnviarLinkAcesso)
    use_case.execute.return_value = {"enviado": True, "link": "https://cademi.com/acesso/abc"}
    tool = EnviarLinkAcessoTool(use_case=use_case)
    fake_config = {"configurable": {"account_id": "acc1"}}
    with patch("agent.skills.enviar_link_acesso.skill.get_config", return_value=fake_config):
        result = await tool._arun(email="joao@email.com", phone="5511999998888")
    assert "enviado com sucesso" in result


@pytest.mark.asyncio
async def test_arun_falha_gerar_link():
    use_case = AsyncMock(spec=EnviarLinkAcesso)
    use_case.execute.return_value = {
        "enviado": False,
        "mensagem": "Não foi possível gerar o link de acesso.",
    }
    tool = EnviarLinkAcessoTool(use_case=use_case)
    fake_config = {"configurable": {"account_id": "acc1"}}
    with patch("agent.skills.enviar_link_acesso.skill.get_config", return_value=fake_config):
        result = await tool._arun(email="joao@email.com", phone="5511999998888")
    assert "Não foi possível" in result
