# tests/unit/capabilities/test_access_send.py
import pytest
from unittest.mock import AsyncMock

from nexoia.application.capabilities.access import AccessState, node_send_access
from nexoia.domain.ports.cademi_port import CademiStudent


def make_state(student, **kwargs) -> AccessState:
    base = dict(
        account_id=1, correlation_id="corr-1", messages=[],
        access_case_id="ac-1", student_email="joao@email.com",
        student_cpf="11122233344", student_name="João",
        student_phone="+5511999999999", cademi_student=student,
        search_attempts=1, cpf_asked=False, access_link=None,
        out_of_scope=False, email_mismatch_pending=False,
        conversation_id="conv-1", purchase_id="p-1", product_name="Curso Python",
    )
    base.update(kwargs)
    return base  # type: ignore[return-value]


@pytest.mark.asyncio
async def test_send_access_skips_when_out_of_scope():
    chatnexo = AsyncMock()
    result = await node_send_access(
        make_state(None, out_of_scope=True),
        cademi_port=AsyncMock(), chatnexo_port=chatnexo,
    )
    chatnexo.send_message.assert_not_called()
    chatnexo.send_template.assert_not_called()
    assert result == {}


@pytest.mark.asyncio
async def test_send_access_skips_when_student_not_found():
    chatnexo = AsyncMock()
    result = await node_send_access(
        make_state(None), cademi_port=AsyncMock(), chatnexo_port=chatnexo,
    )
    chatnexo.send_message.assert_not_called()
    chatnexo.send_template.assert_not_called()
    assert result == {}


@pytest.mark.asyncio
async def test_send_access_skips_when_awaiting_cpf():
    chatnexo = AsyncMock()
    await node_send_access(
        make_state(None, cpf_asked=True), cademi_port=AsyncMock(), chatnexo_port=chatnexo,
    )
    chatnexo.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_send_access_sends_free_text_within_24h():
    student = CademiStudent(id="s1", name="João", email="joao@email.com", phone="+5511999999999")
    cademi = AsyncMock()
    cademi.get_access_link.return_value = "https://cademi.com.br/auto-login/nominal-abc"
    chatnexo = AsyncMock()
    state = make_state(student)
    state["within_24h_window"] = True

    result = await node_send_access(state, cademi_port=cademi, chatnexo_port=chatnexo)

    cademi.get_access_link.assert_awaited_once_with(student_id="s1", product_id="p-1")
    chatnexo.send_message.assert_awaited_once()
    chatnexo.send_template.assert_not_called()
    assert "https://cademi.com.br/auto-login/nominal-abc" in chatnexo.send_message.await_args.kwargs["text"]
    assert result["access_link"] == "https://cademi.com.br/auto-login/nominal-abc"


@pytest.mark.asyncio
async def test_send_access_uses_template_outside_24h():
    student = CademiStudent(id="s1", name="João", email="joao@email.com", phone="+5511999999999")
    cademi = AsyncMock()
    cademi.get_access_link.return_value = "https://cademi.com.br/auto-login/xyz"
    chatnexo = AsyncMock()
    state = make_state(student)
    state["within_24h_window"] = False

    await node_send_access(state, cademi_port=cademi, chatnexo_port=chatnexo)

    chatnexo.send_template.assert_awaited_once()
    assert chatnexo.send_template.await_args.kwargs["template_name"] == "access_reminder_d1"
    chatnexo.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_send_access_defaults_to_template_when_window_unknown():
    student = CademiStudent(id="s1", name="João", email="joao@email.com", phone="+5511999999999")
    cademi = AsyncMock()
    cademi.get_access_link.return_value = "https://cademi.com.br/auto-login/xyz"
    chatnexo = AsyncMock()
    state = make_state(student)
    # within_24h_window absent — fail-closed per RNF-08

    await node_send_access(state, cademi_port=cademi, chatnexo_port=chatnexo)

    chatnexo.send_template.assert_awaited_once()
    chatnexo.send_message.assert_not_called()
