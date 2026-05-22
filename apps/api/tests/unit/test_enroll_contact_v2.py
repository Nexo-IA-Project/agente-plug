"""Testes para EnrollContact v2 — dedup, flow_step_id, jobs órfãos."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.exc import IntegrityError

from shared.application.use_cases.followup.enroll_contact import (
    EnrollContact,
    EnrollResult,
)


def _flow_step(id_, position=1, delay=0):
    return SimpleNamespace(
        id=id_,
        position=position,
        delay_from_purchase_hours=delay,
        meta_template_name="t",
        message_text=None,
        template_variables={},
    )


@pytest.mark.asyncio
async def test_enroll_persists_flow_step_id_on_each_step():
    """Cada enrollment_step criado deve carregar flow_step_id = id do FollowupStep correspondente."""
    fs_id = uuid.uuid4()
    flow = SimpleNamespace(id=uuid.uuid4(), is_active=True)
    flow_repo = AsyncMock()
    flow_repo.find_by_id.return_value = flow
    flow_repo.get_steps.return_value = [_flow_step(fs_id)]

    enrollment_repo = AsyncMock()
    job_repo = AsyncMock()
    job_repo.schedule.return_value = SimpleNamespace(id=uuid.uuid4())

    use_case = EnrollContact(
        flow_repo=flow_repo,
        enrollment_repo=enrollment_repo,
        job_repo=job_repo,
    )
    result = await use_case.execute(
        account_id=uuid.uuid4(),
        contact_id=uuid.uuid4(),
        conversation_id="c1",
        contact_phone="+5511",
        purchase_id="p1",
        flow_id=flow.id,
        customer_name="X",
        product_name="P",
        purchase_time=datetime.now(UTC),
    )
    assert isinstance(result, EnrollResult)
    assert result.enrollment is not None
    assert result.deduped is False

    args, _kwargs = enrollment_repo.create_with_steps.call_args
    steps_arg = args[1]
    assert len(steps_arg) == 1
    assert steps_arg[0].flow_step_id == fs_id


@pytest.mark.asyncio
async def test_enroll_dedup_returns_existing_on_integrity_error():
    """Se UNIQUE constraint dispara IntegrityError, retorna enrollment existente com deduped=True."""
    flow = SimpleNamespace(id=uuid.uuid4(), is_active=True)
    flow_repo = AsyncMock()
    flow_repo.find_by_id.return_value = flow
    flow_repo.get_steps.return_value = [_flow_step(uuid.uuid4())]

    existing = SimpleNamespace(id=uuid.uuid4())
    enrollment_repo = AsyncMock()
    enrollment_repo.create_with_steps.side_effect = IntegrityError("dup", {}, Exception())
    enrollment_repo.find_by_dedup_key.return_value = existing

    job_repo = AsyncMock()
    job_id = uuid.uuid4()
    job_repo.schedule.return_value = SimpleNamespace(id=job_id)

    use_case = EnrollContact(
        flow_repo=flow_repo,
        enrollment_repo=enrollment_repo,
        job_repo=job_repo,
    )
    result = await use_case.execute(
        account_id=uuid.uuid4(),
        contact_id=uuid.uuid4(),
        conversation_id="c",
        contact_phone="+5511",
        purchase_id="dup-id",
        flow_id=flow.id,
        customer_name="X",
        product_name="P",
        purchase_time=datetime.now(UTC),
    )
    assert isinstance(result, EnrollResult)
    assert result.deduped is True
    assert result.enrollment is existing
    # Jobs órfãos devem ser cancelados
    job_repo.cancel.assert_awaited_once_with(job_id)


@pytest.mark.asyncio
async def test_enroll_dedup_rolls_back_session_before_lookup():
    """Após IntegrityError, rollback() deve ser chamado antes de find_by_dedup_key."""
    flow = SimpleNamespace(id=uuid.uuid4(), is_active=True)
    flow_repo = AsyncMock()
    flow_repo.find_by_id.return_value = flow
    flow_repo.get_steps.return_value = [_flow_step(uuid.uuid4())]

    existing = SimpleNamespace(id=uuid.uuid4())
    enrollment_repo = AsyncMock()
    enrollment_repo.create_with_steps.side_effect = IntegrityError("dup", {}, Exception())
    enrollment_repo.find_by_dedup_key.return_value = existing

    job_repo = AsyncMock()
    job_repo.schedule.return_value = SimpleNamespace(id=uuid.uuid4())

    use_case = EnrollContact(
        flow_repo=flow_repo,
        enrollment_repo=enrollment_repo,
        job_repo=job_repo,
    )
    await use_case.execute(
        account_id=uuid.uuid4(),
        contact_id=uuid.uuid4(),
        conversation_id="c",
        contact_phone="+5511",
        purchase_id="dup",
        flow_id=flow.id,
        customer_name="X",
        product_name="P",
        purchase_time=datetime.now(UTC),
    )

    enrollment_repo.rollback.assert_awaited_once()
    # rollback antes do find_by_dedup_key (ordem importa)
    calls = enrollment_repo.method_calls
    rollback_idx = next(i for i, c in enumerate(calls) if c[0] == "rollback")
    lookup_idx = next(i for i, c in enumerate(calls) if c[0] == "find_by_dedup_key")
    assert rollback_idx < lookup_idx


@pytest.mark.asyncio
async def test_enroll_returns_none_when_flow_not_found():
    """Retorno preserva semântica atual: flow inexistente → None (não dedup)."""
    flow_repo = AsyncMock()
    flow_repo.find_by_id.return_value = None

    use_case = EnrollContact(
        flow_repo=flow_repo,
        enrollment_repo=AsyncMock(),
        job_repo=AsyncMock(),
    )
    result = await use_case.execute(
        account_id=uuid.uuid4(),
        contact_id=uuid.uuid4(),
        conversation_id="c",
        contact_phone="+5511",
        purchase_id="x",
        flow_id=uuid.uuid4(),
        customer_name="X",
        product_name="P",
        purchase_time=datetime.now(UTC),
    )
    assert result is None
