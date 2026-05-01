from __future__ import annotations
import pytest
from unittest.mock import AsyncMock, MagicMock
from shared.application.use_cases.access.enviar_link_acesso import EnviarLinkAcesso


def fake_student(name: str = "João Silva", sid: str = "s1"):
    s = MagicMock()
    s.id = sid
    s.name = name
    return s


def fake_case(case_id: str = "case-1", product_name: str = "Mentoria", purchase_id: str = "p1"):
    c = MagicMock()
    c.id = case_id
    c.product_name = product_name
    c.purchase_id = purchase_id
    c.student_cademi_id = "s1"
    return c


@pytest.mark.asyncio
async def test_sends_free_text_within_24h_window():
    repo = AsyncMock()
    repo.find_by_phone.return_value = fake_case()
    cademi = AsyncMock()
    cademi.get_access_link.return_value = "https://cademi.com.br/acesso"
    chatnexo = AsyncMock()
    uc = EnviarLinkAcesso(repo=repo, cademi=cademi, chatnexo=chatnexo)
    result = await uc.execute(
        account_id="t1",
        phone="5511999",
        student_id="s1",
        student_name="João Silva",
        within_24h_window=True,
    )
    chatnexo.send_message.assert_called_once()
    assert "LINK_ENVIADO" in result


@pytest.mark.asyncio
async def test_sends_template_outside_24h_window():
    repo = AsyncMock()
    repo.find_by_phone.return_value = fake_case()
    cademi = AsyncMock()
    cademi.get_access_link.return_value = "https://cademi.com.br/acesso"
    chatnexo = AsyncMock()
    uc = EnviarLinkAcesso(repo=repo, cademi=cademi, chatnexo=chatnexo)
    result = await uc.execute(
        account_id="t1",
        phone="5511999",
        student_id="s1",
        student_name="João Silva",
        within_24h_window=False,
    )
    chatnexo.send_template.assert_called_once()
    assert "LINK_ENVIADO" in result


@pytest.mark.asyncio
async def test_returns_error_when_no_case():
    repo = AsyncMock()
    repo.find_by_phone.return_value = None
    uc = EnviarLinkAcesso(repo=repo, cademi=AsyncMock(), chatnexo=AsyncMock())
    result = await uc.execute(account_id="t1", phone="5511999", student_id="s1", student_name="João")
    assert "ERRO" in result
