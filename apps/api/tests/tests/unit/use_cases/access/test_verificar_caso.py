from __future__ import annotations
import pytest
from unittest.mock import AsyncMock, MagicMock
from nexoia.application.use_cases.access.verificar_caso import VerificarCasoAcesso


def fake_case(case_id: str = "case-1", attempts: int = 0, email: str = "a@b.com"):
    case = MagicMock()
    case.id = case_id
    case.search_attempts = attempts
    case.student_email = email
    return case


@pytest.mark.asyncio
async def test_returns_found_when_case_exists():
    repo = AsyncMock()
    repo.find_by_phone.return_value = fake_case()
    uc = VerificarCasoAcesso(repo=repo, chatnexo=AsyncMock())
    result = await uc.execute(account_id="t1", phone="5511999990000", last_message="quero acesso")
    assert "CASO_ENCONTRADO" in result
    assert "case-1" in result


@pytest.mark.asyncio
async def test_escalates_and_returns_error_when_no_case():
    repo = AsyncMock()
    repo.find_by_phone.return_value = None
    chatnexo = AsyncMock()
    uc = VerificarCasoAcesso(repo=repo, chatnexo=chatnexo)
    result = await uc.execute(account_id="t1", phone="5511999990000", last_message="quero acesso")
    chatnexo.transfer_to_human.assert_called_once()
    assert "ESCALADO" in result


@pytest.mark.asyncio
async def test_escalates_on_shopee_keyword():
    repo = AsyncMock()
    repo.find_by_phone.return_value = fake_case()
    chatnexo = AsyncMock()
    uc = VerificarCasoAcesso(repo=repo, chatnexo=chatnexo)
    result = await uc.execute(account_id="t1", phone="5511999990000", last_message="comprei na shopee")
    chatnexo.transfer_to_human.assert_called_once()
    assert "ESCALADO" in result


@pytest.mark.asyncio
async def test_escalates_on_kyc_keyword():
    repo = AsyncMock()
    repo.find_by_phone.return_value = fake_case()
    chatnexo = AsyncMock()
    uc = VerificarCasoAcesso(repo=repo, chatnexo=chatnexo)
    result = await uc.execute(account_id="t1", phone="5511999990000", last_message="problema com kyc")
    chatnexo.transfer_to_human.assert_called_once()
