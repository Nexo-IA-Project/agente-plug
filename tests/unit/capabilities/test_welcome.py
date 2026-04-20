from unittest.mock import AsyncMock

import pytest

from nexoia.application.capabilities.welcome import (
    WelcomeState,
    node_check_conversation,
    node_fetch_cademi,
    node_schedule_d1,
    node_send_welcome,
)
from nexoia.domain.ports.cademi_port import CademiStudent
from tests.fakes.fake_cademi_client import FakeCademiClient
from tests.fakes.fake_chatnexo_client import FakeChatNexoClient


def make_state(**kwargs) -> WelcomeState:
    base: WelcomeState = {
        "purchase_id": "p-001",
        "account_id": 1,
        "student_name": "João Silva",
        "student_phone": "+5511999999999",
        "student_email": "joao@email.com",
        "product_name": "Curso Python",
        "access_link": None,
        "cademi_attempts": 0,
        "conversation_id": None,
        "access_case_id": None,
        "access_confirmed": False,
        "cademi_failed": False,
        "messages": [],
        "correlation_id": "corr-001",
    }
    base.update(kwargs)  # type: ignore[typeddict-item]
    return base


@pytest.mark.asyncio
async def test_fetch_cademi_happy_path():
    student = CademiStudent(id="s1", name="João Silva", email="joao@email.com", phone="+5511999999999")
    cademi = FakeCademiClient(student=student, access_link="https://cademi.com.br/login/abc")
    state = make_state()

    result = await node_fetch_cademi(state, cademi_port=cademi)

    assert result["access_link"] == "https://cademi.com.br/login/abc"
    assert result["cademi_failed"] is False
    assert result["cademi_attempts"] == 1


@pytest.mark.asyncio
async def test_fetch_cademi_retry_exhausted_sets_failed():
    cademi = FakeCademiClient(student=None, fail_times=3)
    handoff = AsyncMock()
    state = make_state()

    result = await node_fetch_cademi(state, cademi_port=cademi, handoff_fn=handoff, _retry_delay=0.0)

    assert result["cademi_failed"] is True
    assert result["access_link"] is None
    handoff.assert_called_once()


@pytest.mark.asyncio
async def test_check_conversation_uses_existing_open():
    chatnexo = FakeChatNexoClient(open_conversation_id="conv-existing")
    state = make_state()

    result = await node_check_conversation(state, chatnexo_port=chatnexo)

    assert result["conversation_id"] == "conv-existing"


@pytest.mark.asyncio
async def test_check_conversation_creates_new_when_closed():
    chatnexo = FakeChatNexoClient(open_conversation_id=None, new_conversation_id="conv-new")
    state = make_state()

    result = await node_check_conversation(state, chatnexo_port=chatnexo)

    assert result["conversation_id"] == "conv-new"


@pytest.mark.asyncio
async def test_send_welcome_with_link():
    chatnexo = FakeChatNexoClient()
    state = make_state(
        conversation_id="conv-001",
        access_link="https://cademi.com.br/login/abc",
        cademi_failed=False,
    )

    result = await node_send_welcome(state, chatnexo_port=chatnexo)

    assert chatnexo.last_sent_template == "welcome_purchase"
    assert "https://cademi.com.br/login/abc" in str(chatnexo.last_sent_variables)


@pytest.mark.asyncio
async def test_send_welcome_without_link_sends_generic():
    chatnexo = FakeChatNexoClient()
    state = make_state(
        conversation_id="conv-001",
        access_link=None,
        cademi_failed=True,
    )

    await node_send_welcome(state, chatnexo_port=chatnexo)

    assert chatnexo.last_sent_template == "welcome_purchase"
    assert "em instantes" in str(chatnexo.last_sent_variables).lower()


@pytest.mark.asyncio
async def test_schedule_d1_creates_two_jobs():
    scheduler = AsyncMock()
    job_counter = {"n": 0}

    def make_job(*args, **kwargs):
        job_counter["n"] += 1
        return type("Job", (), {"id": f"job-{job_counter['n']}"})()

    scheduler.schedule.side_effect = make_job
    state = make_state(access_case_id="ac-001", conversation_id="conv-001")

    result = await node_schedule_d1(state, scheduler=scheduler)

    assert scheduler.schedule.call_count == 2
    calls = scheduler.schedule.call_args_list
    assert calls[0][1]["job_type"] == "WelcomeCheck"
    assert calls[1][1]["job_type"] == "SendScheduledFollowUp"
    assert "access_reminder_d1" in str(calls[1][1]["payload"])
    assert "scheduled_d1_job_id" in result
    assert "scheduled_check_job_id" in result
