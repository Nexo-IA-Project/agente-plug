from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from agent.skills.access import (
    make_access_skills,
    BuscarAlunoCademiTool,
    EnviarLinkAcessoTool,
    VerificarCasoAcessoTool,
)


def test_make_access_skills_returns_three_tools():
    tools = make_access_skills(
        access_repo=AsyncMock(),
        cademi=AsyncMock(),
        chatnexo=AsyncMock(),
    )
    assert len(tools) == 3
    names = {t.name for t in tools}
    assert "verificar_caso_acesso" in names
    assert "buscar_aluno_cademi" in names
    assert "enviar_link_acesso" in names


@pytest.mark.asyncio
async def test_buscar_aluno_cademi_tool_direct_instantiation():
    buscar_uc = AsyncMock()
    buscar_uc.execute.return_value = "ESCALADO"
    tool = BuscarAlunoCademiTool(buscar_uc=buscar_uc)
    fake_cfg = {"configurable": {"account_id": "t1", "phone": "5511999"}}
    with patch("agent.skills.access.get_config", return_value=fake_cfg):
        result = await tool._arun(email="test@example.com", cpf=None)
    buscar_uc.execute.assert_called_once_with(
        account_id="t1", phone="5511999", email="test@example.com", cpf=None
    )
    assert result == "ESCALADO"


@pytest.mark.asyncio
async def test_verificar_caso_acesso_tool_direct_instantiation():
    verificar_uc = AsyncMock()
    verificar_uc.execute.return_value = "ESCALADO"
    tool = VerificarCasoAcessoTool(verificar_uc=verificar_uc)
    fake_cfg = {"configurable": {"account_id": "t1", "phone": "5511999"}}
    with patch("agent.skills.access.get_config", return_value=fake_cfg):
        result = await tool._arun(last_message="quero acesso")
    verificar_uc.execute.assert_called_once_with(
        account_id="t1", phone="5511999", last_message="quero acesso"
    )
    assert result == "ESCALADO"


@pytest.mark.asyncio
async def test_enviar_link_acesso_tool_direct_instantiation():
    enviar_uc = AsyncMock()
    enviar_uc.execute.return_value = "LINK_ENVIADO: http://cademi.com/x"
    tool = EnviarLinkAcessoTool(enviar_uc=enviar_uc)
    fake_cfg = {"configurable": {"account_id": "t1", "phone": "5511999", "conversation_id": "c1"}}
    with patch("agent.skills.access.get_config", return_value=fake_cfg):
        result = await tool._arun(student_id="s1", student_name="João", within_24h_window=True)
    enviar_uc.execute.assert_called_once_with(
        account_id="t1",
        phone="5511999",
        student_id="s1",
        student_name="João",
        within_24h_window=True,
        conversation_id="c1",
    )
    assert "LINK_ENVIADO" in result
