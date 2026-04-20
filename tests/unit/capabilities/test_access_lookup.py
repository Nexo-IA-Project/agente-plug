from unittest.mock import AsyncMock

import pytest

from nexoia.application.capabilities.access import AccessState, node_lookup_access_case
from nexoia.domain.entities.access_case import AccessCase


def make_state(**kwargs) -> AccessState:
    base = dict(
        account_id=1, correlation_id="corr-1", messages=[],
        access_case_id=None, student_email=None, student_cpf=None,
        student_name=None, student_phone="+5511999999999",
        cademi_student=None, search_attempts=0, cpf_asked=False,
        access_link=None, out_of_scope=False, email_mismatch_pending=False,
    )
    base.update(kwargs)
    return base  # type: ignore[return-value]


@pytest.mark.asyncio
async def test_lookup_populates_state_from_access_case():
    case = AccessCase(account_id=1, contact_id="+5511999999999",
                      conversation_id="conv-1", purchase_id="p-1",
                      product_name="Curso Python")
    case.student_cpf = "111.222.333-44"
    repo = AsyncMock()
    repo.find_by_phone.return_value = case
    handoff = AsyncMock()

    state = make_state()
    result = await node_lookup_access_case(
        state, access_case_repo=repo, chatnexo_port=AsyncMock(), handoff_fn=handoff,
    )

    repo.find_by_phone.assert_awaited_once_with(account_id=1, phone="+5511999999999")
    assert result["access_case_id"] == case.id
    assert result["student_cpf"] == "111.222.333-44"
    handoff.assert_not_called()


@pytest.mark.asyncio
async def test_lookup_triggers_handoff_when_no_case():
    repo = AsyncMock()
    repo.find_by_phone.return_value = None
    handoff = AsyncMock()

    state = make_state()
    result = await node_lookup_access_case(
        state, access_case_repo=repo, chatnexo_port=AsyncMock(), handoff_fn=handoff,
    )

    handoff.assert_awaited_once()
    assert handoff.await_args.kwargs["reason"] == "no_access_case"
    assert result["access_case_id"] is None


@pytest.mark.asyncio
async def test_lookup_respects_account_id_isolation():
    repo = AsyncMock()
    repo.find_by_phone.return_value = None
    handoff = AsyncMock()

    state = make_state(account_id=42, student_phone="+5511999999991")
    await node_lookup_access_case(
        state, access_case_repo=repo, chatnexo_port=AsyncMock(), handoff_fn=handoff,
    )
    repo.find_by_phone.assert_awaited_once_with(account_id=42, phone="+5511999999991")
