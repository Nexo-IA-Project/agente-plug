"""
Teste end-to-end da Capability Welcome usando fakes de infraestrutura.
Requer DB real (marca @pytest.mark.integration — skipped localmente).
"""
import pytest
from nexoia.domain.entities.access_case import AccessCaseStatus
from nexoia.domain.ports.cademi_port import CademiStudent
from nexoia.infrastructure.db.repositories.access_case_repo import AccessCaseRepository
from nexoia.application.capabilities.welcome import (
    WelcomeState,
    node_fetch_cademi,
    node_check_conversation,
    node_send_welcome,
    node_persist_access_case,
    node_schedule_d1,
)
from tests.fakes.fake_cademi_client import FakeCademiClient
from tests.fakes.fake_chatnexo_client import FakeChatNexoClient
from unittest.mock import AsyncMock


@pytest.fixture
def student():
    return CademiStudent(
        id="student-001",
        name="Maria Souza",
        email="maria@email.com",
        phone="+5511988888888",
    )


@pytest.fixture
def initial_state(student) -> WelcomeState:
    return {
        "purchase_id": "purchase-integration-001",
        "account_id": 1,
        "student_name": student.name,
        "student_phone": student.phone,
        "student_email": student.email,
        "product_name": "Curso de Vendas",
        "access_link": None,
        "cademi_attempts": 0,
        "conversation_id": None,
        "access_case_id": None,
        "access_confirmed": False,
        "cademi_failed": False,
        "messages": [],
        "correlation_id": "corr-integration-001",
    }


@pytest.mark.asyncio
@pytest.mark.integration
async def test_full_happy_path(db_session, initial_state, student):
    cademi = FakeCademiClient(
        student=student,
        access_link="https://cademi.com.br/auto-login/maria-token",
    )
    chatnexo = FakeChatNexoClient(
        open_conversation_id=None,
        new_conversation_id="conv-new-001",
    )
    scheduler_mock = AsyncMock()
    scheduler_mock.schedule.return_value = type("Job", (), {"id": "job-d1-001"})()
    repo = AccessCaseRepository(db_session)

    state = dict(initial_state)
    state.update(await node_fetch_cademi(initial_state, cademi_port=cademi))
    state.update(await node_check_conversation(state, chatnexo_port=chatnexo))
    state.update(await node_send_welcome(state, chatnexo_port=chatnexo))
    state.update(await node_persist_access_case(state, access_case_repo=repo))
    await node_schedule_d1(state, scheduler=scheduler_mock)

    saved = await repo.get_by_purchase_id("purchase-integration-001")
    assert saved is not None
    assert saved.status == AccessCaseStatus.LINK_SENT
    assert saved.access_link == "https://cademi.com.br/auto-login/maria-token"

    scheduler_mock.schedule.assert_called_once()
    call_kwargs = scheduler_mock.schedule.call_args[1]
    assert call_kwargs["payload"]["template"] == "access_reminder_d1"

    assert chatnexo.last_sent_template == "welcome_purchase"
    assert "https://cademi.com.br/auto-login/maria-token" in str(chatnexo.last_sent_variables)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_cademi_failure_flow(db_session, initial_state):
    cademi = FakeCademiClient(student=None, fail_times=3)
    chatnexo = FakeChatNexoClient(open_conversation_id="conv-existing")
    scheduler_mock = AsyncMock()
    scheduler_mock.schedule.return_value = type("Job", (), {"id": "job-d1-002"})()
    handoff = AsyncMock()
    repo = AccessCaseRepository(db_session)

    state = dict(initial_state)
    state.update(await node_fetch_cademi(initial_state, cademi_port=cademi, handoff_fn=handoff, _retry_delay=0.0))
    state.update(await node_check_conversation(state, chatnexo_port=chatnexo))
    state.update(await node_send_welcome(state, chatnexo_port=chatnexo))
    state.update(await node_persist_access_case(state, access_case_repo=repo))
    await node_schedule_d1(state, scheduler=scheduler_mock)

    handoff.assert_called_once()

    saved = await repo.get_by_purchase_id("purchase-integration-001")
    assert saved.status == AccessCaseStatus.ESCALATED

    assert "em instantes" in str(chatnexo.last_sent_variables).lower()
