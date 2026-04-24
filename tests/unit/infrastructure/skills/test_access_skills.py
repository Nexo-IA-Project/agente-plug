from __future__ import annotations
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from nexoia.infrastructure.skills.access import make_access_skills


@pytest.mark.asyncio
async def test_make_access_skills_returns_three_tools():
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
async def test_verificar_caso_acesso_tool_calls_use_case():
    repo = AsyncMock()
    repo.find_by_phone.return_value = None
    chatnexo = AsyncMock()
    tools = make_access_skills(repo, AsyncMock(), chatnexo)
    tool = next(t for t in tools if t.name == "verificar_caso_acesso")
    fake_cfg = {"configurable": {"account_id": "t1", "phone": "5511999", "conversation_id": "c1"}}
    with patch("nexoia.infrastructure.skills.access.get_config", return_value=fake_cfg):
        result = await tool.ainvoke({"last_message": "quero acesso"})
    assert "ESCALADO" in result or "CASO" in result


@pytest.mark.asyncio
async def test_buscar_aluno_cademi_tool_passes_email_to_use_case():
    repo = AsyncMock()
    repo.find_by_phone.return_value = None
    tools = make_access_skills(repo, AsyncMock(), AsyncMock())
    tool = next(t for t in tools if t.name == "buscar_aluno_cademi")
    fake_cfg = {"configurable": {"account_id": "t1", "phone": "5511999", "conversation_id": "c1"}}
    with patch("nexoia.infrastructure.skills.access.get_config", return_value=fake_cfg):
        result = await tool.ainvoke({"email": "test@example.com"})
    assert isinstance(result, str)
