from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from shared.application.use_cases.onboarding.enroll_contact import EnrollContact
from shared.domain.entities.onboarding import (
    EnrollmentStatus,
    OnboardingFlow,
    OnboardingStep,
)


def _fake_session() -> MagicMock:
    """Sessão fake com begin_nested() como async context manager."""
    session = MagicMock()
    nested_ctx = MagicMock()
    nested_ctx.__aenter__ = AsyncMock(return_value=None)
    nested_ctx.__aexit__ = AsyncMock(return_value=False)
    session.begin_nested = MagicMock(return_value=nested_ctx)
    return session


_ACCOUNT_ID = UUID("00000000-0000-0000-0000-000000000001")
_CONTACT_ID = uuid4()
_CONV_ID = "conv-external-123"
_FLOW_ID = uuid4()
_COURSE_ID = uuid4()


def _make_flow(is_active: bool = True) -> OnboardingFlow:
    return OnboardingFlow(
        id=_FLOW_ID,
        account_id=_ACCOUNT_ID,
        product_id=_COURSE_ID,
        name="Máquina de Vendas",
        is_active=is_active,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def _make_step(position: int, delay: int) -> OnboardingStep:
    return OnboardingStep(
        id=uuid4(),
        flow_id=_FLOW_ID,
        position=position,
        delay_from_previous_minutes=delay,
        meta_template_name=f"mv_template_{position}",
        template_variables={},
        created_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_enroll_contact_creates_enrollment_with_snapshots_and_schedules_jobs():
    flow_repo = AsyncMock()
    flow_repo.find_by_id.return_value = _make_flow()
    flow_repo.get_steps.return_value = [
        _make_step(1, 0),
        _make_step(2, 1),
        _make_step(3, 24),
    ]

    enrollment_repo = AsyncMock()
    enrollment_repo.create_with_steps = AsyncMock(return_value=None)

    job_repo = AsyncMock()
    fake_job = MagicMock()
    fake_job.id = uuid4()
    job_repo.schedule = AsyncMock(return_value=fake_job)

    purchase_time = datetime.now(UTC)
    uc = EnrollContact(
        session=_fake_session(),
        flow_repo=flow_repo,
        enrollment_repo=enrollment_repo,
        job_repo=job_repo,
    )

    result = await uc.execute(
        account_id=_ACCOUNT_ID,
        contact_id=_CONTACT_ID,
        conversation_id=_CONV_ID,
        contact_phone="5511999990000",
        purchase_id="p-001",
        flow_id=_FLOW_ID,
        customer_name="Fabio",
        product_name="Máquina de Vendas",
        purchase_time=purchase_time,
    )

    assert result is not None
    assert result.deduped is False
    enrollment = result.enrollment
    assert enrollment is not None
    assert enrollment.status == EnrollmentStatus.ACTIVE
    assert enrollment.flow_id == _FLOW_ID
    assert enrollment.customer_name == "Fabio"
    assert enrollment.product_name == "Máquina de Vendas"
    assert job_repo.schedule.call_count == 3

    enrollment_repo.create_with_steps.assert_awaited_once()
    args, _kwargs = enrollment_repo.create_with_steps.call_args
    enrollment_arg, steps_arg = args
    assert enrollment_arg.customer_name == "Fabio"
    assert enrollment_arg.product_name == "Máquina de Vendas"
    assert len(steps_arg) == 3

    flow_repo.find_by_id.assert_awaited_once_with(_FLOW_ID)


@pytest.mark.asyncio
async def test_enroll_contact_returns_none_when_flow_not_found():
    flow_repo = AsyncMock()
    flow_repo.find_by_id.return_value = None

    uc = EnrollContact(
        session=_fake_session(),
        flow_repo=flow_repo,
        enrollment_repo=AsyncMock(),
        job_repo=AsyncMock(),
    )

    result = await uc.execute(
        account_id=_ACCOUNT_ID,
        contact_id=_CONTACT_ID,
        conversation_id=_CONV_ID,
        contact_phone="5511999990000",
        purchase_id="p-001",
        flow_id=_FLOW_ID,
        customer_name="Fabio",
        product_name="Curso X",
        purchase_time=datetime.now(UTC),
    )

    assert result is None


@pytest.mark.asyncio
async def test_enroll_contact_returns_none_when_flow_inactive():
    flow_repo = AsyncMock()
    flow_repo.find_by_id.return_value = _make_flow(is_active=False)

    uc = EnrollContact(
        session=_fake_session(),
        flow_repo=flow_repo,
        enrollment_repo=AsyncMock(),
        job_repo=AsyncMock(),
    )

    result = await uc.execute(
        account_id=_ACCOUNT_ID,
        contact_id=_CONTACT_ID,
        conversation_id=_CONV_ID,
        contact_phone="5511999990000",
        purchase_id="p-001",
        flow_id=_FLOW_ID,
        customer_name="Fabio",
        product_name="Curso X",
        purchase_time=datetime.now(UTC),
    )

    assert result is None


@pytest.mark.asyncio
async def test_enroll_contact_returns_none_when_flow_has_no_steps():
    flow_repo = AsyncMock()
    flow_repo.find_by_id.return_value = _make_flow()
    flow_repo.get_steps.return_value = []

    uc = EnrollContact(
        session=_fake_session(),
        flow_repo=flow_repo,
        enrollment_repo=AsyncMock(),
        job_repo=AsyncMock(),
    )

    result = await uc.execute(
        account_id=_ACCOUNT_ID,
        contact_id=_CONTACT_ID,
        conversation_id=_CONV_ID,
        contact_phone="5511999990000",
        purchase_id="p-001",
        flow_id=_FLOW_ID,
        customer_name="Fabio",
        product_name="Curso X",
        purchase_time=datetime.now(UTC),
    )

    assert result is None
