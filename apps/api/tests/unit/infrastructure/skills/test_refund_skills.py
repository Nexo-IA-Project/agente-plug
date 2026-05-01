from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from agent.skills.refund import (
    make_refund_skills,
    VerificarElegibilidadeReembolsoTool,
    OfereceRetencaoTool,
    ProcessarReembolsoTool,
)


def test_make_refund_skills_returns_three_tools():
    skills = make_refund_skills(
        refund_repo=AsyncMock(),
        hubla=AsyncMock(),
        legal_history=AsyncMock(),
        refund_mutex=AsyncMock(),
    )
    assert len(skills) == 3


def test_make_refund_skills_tool_names():
    skills = make_refund_skills(
        refund_repo=AsyncMock(),
        hubla=AsyncMock(),
        legal_history=AsyncMock(),
        refund_mutex=AsyncMock(),
    )
    names = {s.name for s in skills}
    assert names == {
        "verificar_elegibilidade_reembolso",
        "oferecer_retencao",
        "processar_reembolso",
    }


@pytest.mark.asyncio
async def test_verificar_elegibilidade_tool_calls_use_case():
    verificar_uc = AsyncMock()
    verificar_uc.execute.return_value = "ELEGIVEL"
    tool = VerificarElegibilidadeReembolsoTool(verificar_uc=verificar_uc)
    fake_cfg = {"configurable": {"account_id": 1, "phone": "5511999", "conversation_id": "c1"}}
    with patch("nexoia.infrastructure.skills.refund.get_config", return_value=fake_cfg):
        result = await tool._arun(motivo="arrependimento", email="a@b.com", cpf="12345678901")
    verificar_uc.execute.assert_called_once_with(1, "5511999", "c1", "arrependimento", "a@b.com", "12345678901")
    assert result == "ELEGIVEL"


@pytest.mark.asyncio
async def test_oferecer_retencao_tool_calls_use_case():
    reter_uc = AsyncMock()
    reter_uc.execute.return_value = "Oferta N1: ..."
    tool = OfereceRetencaoTool(reter_uc=reter_uc)
    fake_cfg = {"configurable": {"account_id": 1, "phone": "5511999"}}
    with patch("nexoia.infrastructure.skills.refund.get_config", return_value=fake_cfg):
        result = await tool._arun()
    reter_uc.execute.assert_called_once_with(1, "5511999")
    assert "Oferta" in result


@pytest.mark.asyncio
async def test_processar_reembolso_tool_calls_use_case():
    processar_uc = AsyncMock()
    processar_uc.execute.return_value = "Tô processando seu reembolso agora!"
    tool = ProcessarReembolsoTool(processar_uc=processar_uc)
    fake_cfg = {"configurable": {"account_id": 1, "phone": "5511999"}}
    with patch("nexoia.infrastructure.skills.refund.get_config", return_value=fake_cfg):
        result = await tool._arun()
    processar_uc.execute.assert_called_once_with(1, "5511999")
    assert "reembolso" in result.lower()
