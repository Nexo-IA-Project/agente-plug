# tests/unit/capabilities/test_access_cascade.py
import pytest
from unittest.mock import AsyncMock

from nexoia.application.capabilities.access import AccessState, node_search_cademi_cascade
from nexoia.domain.ports.cademi_port import CademiStudent
from tests.fakes.fake_cademi_client import FakeCademiClient


def make_state(**kwargs) -> AccessState:
    base = dict(
        account_id=1, correlation_id="corr-1",
        messages=[{"role": "user", "content": "não consigo acessar"}],
        access_case_id="ac-1", student_email="joao@email.com",
        student_cpf=None, student_name="João",
        student_phone="+5511999999999", cademi_student=None,
        search_attempts=0, cpf_asked=False, access_link=None,
        out_of_scope=False, email_mismatch_pending=False,
    )
    base.update(kwargs)
    return base  # type: ignore[return-value]


@pytest.mark.asyncio
async def test_cascade_skips_when_out_of_scope():
    cademi = FakeCademiClient()
    result = await node_search_cademi_cascade(
        make_state(out_of_scope=True),
        cademi_port=cademi, chatnexo_port=AsyncMock(), handoff_fn=AsyncMock(),
    )
    assert result == {}
    assert cademi.email_calls == 0


@pytest.mark.asyncio
async def test_cascade_found_by_email_on_first_attempt():
    alice = CademiStudent(id="s1", name="João", email="joao@email.com", phone="+5511999999999")
    cademi = FakeCademiClient(students_by_email={"joao@email.com": alice})
    result = await node_search_cademi_cascade(
        make_state(),
        cademi_port=cademi, chatnexo_port=AsyncMock(), handoff_fn=AsyncMock(),
    )
    assert result["cademi_student"] == alice
    assert result["search_attempts"] == 1


@pytest.mark.asyncio
async def test_cascade_falls_back_to_cpf_when_email_misses():
    bob = CademiStudent(id="s2", name="João", email="joao2@email.com", phone="+5511999999999")
    cademi = FakeCademiClient(students_by_email={}, students_by_cpf={"11122233344": bob})
    result = await node_search_cademi_cascade(
        make_state(student_cpf="11122233344"),
        cademi_port=cademi, chatnexo_port=AsyncMock(), handoff_fn=AsyncMock(),
    )
    assert result["cademi_student"] == bob
    assert result["search_attempts"] == 2
    assert cademi.email_calls == 1
    assert cademi.cpf_calls == 1


@pytest.mark.asyncio
async def test_cascade_asks_cpf_when_not_available():
    cademi = FakeCademiClient(students_by_email={})
    chatnexo = AsyncMock()
    result = await node_search_cademi_cascade(
        make_state(student_cpf=None),
        cademi_port=cademi, chatnexo_port=chatnexo, handoff_fn=AsyncMock(),
    )
    chatnexo.send_message.assert_awaited_once()
    assert result["cpf_asked"] is True
    assert result.get("cademi_student") is None
    assert result["search_attempts"] == 1
    assert cademi.cpf_calls == 0


@pytest.mark.asyncio
async def test_cascade_consumes_cpf_from_next_turn():
    student = CademiStudent(id="s3", name="Maria", email="x@x.com", phone="+5511988888888")
    cademi = FakeCademiClient(students_by_email={}, students_by_cpf={"98765432100": student})
    state = make_state(
        student_cpf=None, cpf_asked=True, search_attempts=1,
        messages=[
            {"role": "user", "content": "não consigo acessar"},
            {"role": "assistant", "content": "me passa seu cpf"},
            {"role": "user", "content": "987.654.321-00"},
        ],
    )
    result = await node_search_cademi_cascade(
        state, cademi_port=cademi, chatnexo_port=AsyncMock(), handoff_fn=AsyncMock(),
    )
    assert result["cademi_student"] == student
    assert result["student_cpf"] == "98765432100"
    assert result["search_attempts"] == 2


@pytest.mark.asyncio
async def test_cascade_name_phone_raises_not_implemented_by_default():
    cademi = FakeCademiClient(students_by_email={}, students_by_cpf={}, name_phone_supported=False)
    handoff = AsyncMock()
    result = await node_search_cademi_cascade(
        make_state(student_cpf="99988877766"),
        cademi_port=cademi, chatnexo_port=AsyncMock(), handoff_fn=handoff,
    )
    assert result.get("cademi_student") is None
    assert result["search_attempts"] == 3
    handoff.assert_awaited_once()
    assert handoff.await_args.kwargs["reason"] == "cademi_not_found_after_3_attempts"


@pytest.mark.asyncio
async def test_cascade_escalates_after_3_attempts_even_if_name_phone_supported():
    cademi = FakeCademiClient(students_by_email={}, students_by_cpf={},
                              students_by_name_phone={}, name_phone_supported=True)
    handoff = AsyncMock()
    result = await node_search_cademi_cascade(
        make_state(student_cpf="11122233344"),
        cademi_port=cademi, chatnexo_port=AsyncMock(), handoff_fn=handoff,
    )
    assert result.get("cademi_student") is None
    assert result["search_attempts"] == 3
    handoff.assert_awaited_once()


@pytest.mark.asyncio
async def test_cascade_email_mismatch_pending_triggers_offer():
    cademi = FakeCademiClient(students_by_email={})
    chatnexo = AsyncMock()
    state = make_state(
        student_email="joao@email.com",
        messages=[{"role": "user", "content": "tentei entrar com joao.novo@gmail.com"}],
    )
    result = await node_search_cademi_cascade(
        state, cademi_port=cademi, chatnexo_port=chatnexo, handoff_fn=AsyncMock(),
    )
    assert result["email_mismatch_pending"] is True
    chatnexo.send_message.assert_awaited_once()
    assert cademi.email_calls == 0


@pytest.mark.asyncio
async def test_cascade_email_mismatch_updates_and_searches_on_confirm():
    alice = CademiStudent(id="s1", name="João", email="joao.novo@gmail.com", phone="+5511999999999")
    cademi = FakeCademiClient(students_by_email={"joao.novo@gmail.com": alice})
    state = make_state(
        student_email="joao.novo@gmail.com", email_mismatch_pending=False,
        messages=[{"role": "user", "content": "pode atualizar sim"}],
    )
    result = await node_search_cademi_cascade(
        state, cademi_port=cademi, chatnexo_port=AsyncMock(), handoff_fn=AsyncMock(),
    )
    assert result["cademi_student"] == alice


@pytest.mark.asyncio
async def test_cascade_cpf_invalid_in_message_asks_again():
    cademi = FakeCademiClient(students_by_email={}, students_by_cpf={})
    chatnexo = AsyncMock()
    state = make_state(
        student_cpf=None, cpf_asked=True, search_attempts=1,
        messages=[
            {"role": "user", "content": "não consigo acessar"},
            {"role": "assistant", "content": "me passa seu cpf"},
            {"role": "user", "content": "não sei direito, é tipo 123"},
        ],
    )
    result = await node_search_cademi_cascade(
        state, cademi_port=cademi, chatnexo_port=chatnexo, handoff_fn=AsyncMock(),
    )
    assert result["cpf_asked"] is True
    assert cademi.cpf_calls == 0
