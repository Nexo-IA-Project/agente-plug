from __future__ import annotations
import pytest
from unittest.mock import AsyncMock, MagicMock
from shared.application.use_cases.access.buscar_aluno_cademi import BuscarAlunoCademi


def fake_student(name: str = "João Silva", sid: str = "s1"):
    s = MagicMock()
    s.id = sid
    s.name = name
    return s


def fake_case(attempts: int = 0, email: str = "joao@test.com", cpf: str | None = None):
    c = MagicMock()
    c.id = "case-1"
    c.search_attempts = attempts
    c.student_email = email
    c.student_cpf = cpf
    return c


@pytest.mark.asyncio
async def test_finds_student_by_email_on_first_attempt():
    repo = AsyncMock()
    repo.find_by_phone.return_value = fake_case()
    cademi = AsyncMock()
    cademi.get_student_by_email.return_value = fake_student()
    uc = BuscarAlunoCademi(repo=repo, cademi=cademi)
    result = await uc.execute(account_id="t1", phone="5511999", email="joao@test.com")
    assert "ENCONTRADO" in result
    assert "João Silva" in result


@pytest.mark.asyncio
async def test_falls_back_to_cpf_when_email_fails():
    repo = AsyncMock()
    repo.find_by_phone.return_value = fake_case(attempts=1)
    cademi = AsyncMock()
    cademi.get_student_by_email.return_value = None
    cademi.get_student_by_cpf.return_value = fake_student("Maria Souza")
    uc = BuscarAlunoCademi(repo=repo, cademi=cademi)
    result = await uc.execute(account_id="t1", phone="5511999", email="x@x.com", cpf="12345678901")
    assert "ENCONTRADO" in result
    assert "Maria Souza" in result


@pytest.mark.asyncio
async def test_returns_ask_cpf_when_cpf_missing_and_email_failed():
    repo = AsyncMock()
    repo.find_by_phone.return_value = fake_case(attempts=1)
    cademi = AsyncMock()
    cademi.get_student_by_email.return_value = None
    uc = BuscarAlunoCademi(repo=repo, cademi=cademi)
    result = await uc.execute(account_id="t1", phone="5511999", email="x@x.com", cpf=None)
    assert "CPF" in result


@pytest.mark.asyncio
async def test_escalates_after_max_attempts():
    repo = AsyncMock()
    repo.find_by_phone.return_value = fake_case(attempts=3)
    cademi = AsyncMock()
    cademi.get_student_by_email.return_value = None
    cademi.get_student_by_cpf.return_value = None
    cademi.get_student_by_name_phone.return_value = None
    uc = BuscarAlunoCademi(repo=repo, cademi=cademi)
    result = await uc.execute(account_id="t1", phone="5511999", email="x@x.com", cpf="00000000000")
    assert "ESCALADO" in result


@pytest.mark.asyncio
async def test_returns_not_found_when_case_missing():
    repo = AsyncMock()
    repo.find_by_phone.return_value = None
    uc = BuscarAlunoCademi(repo=repo, cademi=AsyncMock())
    result = await uc.execute(account_id="t1", phone="5511999")
    assert "CASO_NAO_ENCONTRADO" in result
