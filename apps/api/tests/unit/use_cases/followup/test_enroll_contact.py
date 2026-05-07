from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from shared.application.use_cases.followup.enroll_contact import EnrollContact
from shared.domain.entities.followup import (
    EnrollmentStatus,
    FollowupFlow,
    FollowupStep,
)

_ACCOUNT_ID = UUID("00000000-0000-0000-0000-000000000001")
_CONTACT_ID = uuid4()
_CONV_ID = uuid4()
_FLOW_ID = uuid4()


def _make_flow() -> FollowupFlow:
    return FollowupFlow(
        id=_FLOW_ID,
        account_id=_ACCOUNT_ID,
        name="Máquina de Vendas",
        product_tags=["maquina_de_vendas"],
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def _make_step(position: int, delay: int) -> FollowupStep:
    return FollowupStep(
        id=uuid4(),
        flow_id=_FLOW_ID,
        position=position,
        delay_from_purchase_hours=delay,
        meta_template_name=f"mv_template_{position}",
        template_variables={},
        created_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_enroll_contact_creates_enrollment_and_schedules_jobs():
    flow_repo = AsyncMock()
    flow_repo.find_active_by_product.return_value = _make_flow()
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
    uc = EnrollContact(flow_repo=flow_repo, enrollment_repo=enrollment_repo, job_repo=job_repo)

    result = await uc.execute(
        account_id=_ACCOUNT_ID,
        contact_id=_CONTACT_ID,
        conversation_id=_CONV_ID,
        contact_phone="5511999990000",
        purchase_id="p-001",
        product="maquina_de_vendas Curso",
        purchase_time=purchase_time,
    )

    assert result is not None
    assert result.status == EnrollmentStatus.ACTIVE
    assert result.flow_id == _FLOW_ID
    assert job_repo.schedule.call_count == 3
    enrollment_repo.create_with_steps.assert_called_once()


@pytest.mark.asyncio
async def test_enroll_contact_returns_none_when_no_flow_found():
    flow_repo = AsyncMock()
    flow_repo.find_active_by_product.return_value = None

    uc = EnrollContact(
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
        product="produto_desconhecido",
        purchase_time=datetime.now(UTC),
    )

    assert result is None
