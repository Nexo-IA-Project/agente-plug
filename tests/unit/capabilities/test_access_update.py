# tests/unit/capabilities/test_access_update.py
import pytest
from unittest.mock import AsyncMock

from nexoia.application.capabilities.access import AccessState, node_update_access_case
from nexoia.domain.entities.access_case import AccessCaseStatus
from nexoia.domain.ports.cademi_port import CademiStudent


def make_state(**kwargs) -> AccessState:
    base = dict(
        account_id=1, correlation_id="corr-1", messages=[],
        access_case_id="ac-1", student_email="joao@email.com",
        student_cpf="11122233344", student_name="João",
        student_phone="+5511999999999", cademi_student=None,
        search_attempts=1, cpf_asked=False, access_link=None,
        out_of_scope=False, email_mismatch_pending=False,
    )
    base.update(kwargs)
    return base  # type: ignore[return-value]


@pytest.mark.asyncio
async def test_update_sets_reactive_link_sent_when_link_sent():
    repo = AsyncMock()
    state = make_state(
        cademi_student=CademiStudent(id="s1", name="João", email="j@e.com", phone=None),
        access_link="https://cademi.com.br/auto-login/abc",
        search_attempts=1,
    )
    await node_update_access_case(state, access_case_repo=repo)
    repo.update_status.assert_awaited_once_with(
        case_id="ac-1", status=AccessCaseStatus.REACTIVE_LINK_SENT, search_attempts=1,
    )


@pytest.mark.asyncio
async def test_update_sets_reactive_escalated_when_no_link():
    repo = AsyncMock()
    state = make_state(cademi_student=None, access_link=None, search_attempts=3)
    await node_update_access_case(state, access_case_repo=repo)
    repo.update_status.assert_awaited_once_with(
        case_id="ac-1", status=AccessCaseStatus.REACTIVE_ESCALATED, search_attempts=3,
    )


@pytest.mark.asyncio
async def test_update_noop_when_no_access_case():
    repo = AsyncMock()
    await node_update_access_case(make_state(access_case_id=None), access_case_repo=repo)
    repo.update_status.assert_not_called()


@pytest.mark.asyncio
async def test_update_noop_when_out_of_scope():
    repo = AsyncMock()
    await node_update_access_case(make_state(out_of_scope=True), access_case_repo=repo)
    repo.update_status.assert_not_called()


@pytest.mark.asyncio
async def test_update_noop_when_awaiting_cpf():
    repo = AsyncMock()
    await node_update_access_case(
        make_state(cpf_asked=True, cademi_student=None, access_link=None),
        access_case_repo=repo,
    )
    repo.update_status.assert_not_called()


@pytest.mark.asyncio
async def test_update_noop_when_email_mismatch_pending():
    repo = AsyncMock()
    await node_update_access_case(make_state(email_mismatch_pending=True), access_case_repo=repo)
    repo.update_status.assert_not_called()
