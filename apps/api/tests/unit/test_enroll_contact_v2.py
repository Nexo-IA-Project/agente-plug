"""Testes para EnrollContact v2 — dedup, flow_step_id, savepoint isolado."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

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


def _make_session() -> MagicMock:
    """Sessão fake com begin_nested() funcionando como async context manager."""
    session = MagicMock()
    nested_ctx = MagicMock()
    nested_ctx.__aenter__ = AsyncMock(return_value=None)
    nested_ctx.__aexit__ = AsyncMock(return_value=False)
    session.begin_nested = MagicMock(return_value=nested_ctx)
    return session


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
        session=_make_session(),
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
        session=_make_session(),
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
    # Jobs órfãos NÃO são cancelados manualmente — o rollback da savepoint
    # já reverte os inserts de scheduled_jobs feitos dentro dela.
    job_repo.cancel.assert_not_called()


@pytest.mark.asyncio
async def test_enroll_dedup_uses_savepoint_to_isolate_failure():
    """A criação roda dentro de session.begin_nested() (SAVEPOINT) — em caso de
    IntegrityError, a sessão pai permanece utilizável e find_by_dedup_key é chamado."""
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

    session = _make_session()
    use_case = EnrollContact(
        session=session,
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

    # Verifica que begin_nested foi chamado (savepoint usado)
    session.begin_nested.assert_called_once()
    # E que o lookup foi feito após a savepoint reverter
    enrollment_repo.find_by_dedup_key.assert_awaited_once()


@pytest.mark.asyncio
async def test_enroll_returns_none_when_flow_not_found():
    """Retorno preserva semântica atual: flow inexistente → None (não dedup)."""
    flow_repo = AsyncMock()
    flow_repo.find_by_id.return_value = None

    use_case = EnrollContact(
        session=_make_session(),
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
