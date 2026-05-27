import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from shared.application.use_cases.onboarding.resync_enrollment import (
    ResyncEnrollmentUseCase,
)
from shared.domain.entities.onboarding import EnrollmentStepStatus


def _make_use_case(flow_steps, enrollment_steps):
    enrollment = SimpleNamespace(
        id=uuid.uuid4(),
        purchase_time=datetime.now(UTC),
        steps=enrollment_steps,
        conversation_id="conv-1",
        contact_phone="+5511999",
    )
    enrollment_repo = AsyncMock()
    enrollment_repo.get_with_steps.return_value = enrollment
    flow_step_repo = AsyncMock()
    flow_step_repo.get_steps.return_value = flow_steps
    scheduled_job_repo = AsyncMock()
    new_job_id = uuid.uuid4()
    scheduled_job_repo.schedule.return_value = SimpleNamespace(id=new_job_id)

    use_case = ResyncEnrollmentUseCase(
        enrollment_repo=enrollment_repo,
        flow_step_repo=flow_step_repo,
        scheduled_job_repo=scheduled_job_repo,
    )
    return use_case, enrollment, enrollment_repo, flow_step_repo, scheduled_job_repo


@pytest.mark.asyncio
async def test_resync_adds_new_step():
    new_fs_id = uuid.uuid4()
    flow_steps = [
        SimpleNamespace(
            id=new_fs_id,
            position=1,
            delay_from_previous_minutes=0,
            meta_template_name="t",
            message_text=None,
            template_variables={},
        )
    ]
    use_case, enrollment, enrollment_repo, _, sched_repo = _make_use_case(flow_steps, [])
    audit = await use_case.execute(
        enrollment_id=enrollment.id, flow_id=uuid.uuid4(), account_id=uuid.uuid4()
    )
    assert audit["steps_added"] == 1
    enrollment_repo.add_step_with_job.assert_awaited()
    sched_repo.schedule.assert_awaited()


@pytest.mark.asyncio
async def test_resync_reschedules_when_delay_changed():
    fs_id = uuid.uuid4()
    old_job = uuid.uuid4()
    flow_steps = [
        SimpleNamespace(
            id=fs_id,
            position=1,
            delay_from_previous_minutes=48,
            meta_template_name="t",
            message_text=None,
            template_variables={},
        )
    ]
    enr_step = SimpleNamespace(
        id=uuid.uuid4(),
        flow_step_id=fs_id,
        position=1,
        delay_from_previous_minutes=24,
        status=EnrollmentStepStatus.PENDING,
        meta_template_name="t",
        message_text=None,
        template_variables={},
        scheduled_job_id=old_job,
    )
    use_case, enrollment, _enrollment_repo, _, sched_repo = _make_use_case(flow_steps, [enr_step])
    audit = await use_case.execute(
        enrollment_id=enrollment.id, flow_id=uuid.uuid4(), account_id=uuid.uuid4()
    )
    assert audit["steps_rescheduled"] == 1
    sched_repo.cancel.assert_awaited_with(old_job)


@pytest.mark.asyncio
async def test_resync_updates_content_when_only_content_changed():
    fs_id = uuid.uuid4()
    flow_steps = [
        SimpleNamespace(
            id=fs_id,
            position=1,
            delay_from_previous_minutes=24,
            meta_template_name="new_template",
            message_text=None,
            template_variables={},
        )
    ]
    enr_step = SimpleNamespace(
        id=uuid.uuid4(),
        flow_step_id=fs_id,
        position=1,
        delay_from_previous_minutes=24,
        status=EnrollmentStepStatus.PENDING,
        meta_template_name="old_template",
        message_text=None,
        template_variables={},
        scheduled_job_id=uuid.uuid4(),
    )
    use_case, enrollment, enrollment_repo, _, sched_repo = _make_use_case(flow_steps, [enr_step])
    audit = await use_case.execute(
        enrollment_id=enrollment.id, flow_id=uuid.uuid4(), account_id=uuid.uuid4()
    )
    assert audit["steps_content_updated"] == 1
    sched_repo.cancel.assert_not_awaited()  # delay não mudou
    enrollment_repo.apply_step_update.assert_awaited()


@pytest.mark.asyncio
async def test_resync_cancels_removed_steps():
    fs_id = uuid.uuid4()
    enr_step = SimpleNamespace(
        id=uuid.uuid4(),
        flow_step_id=fs_id,
        position=1,
        delay_from_previous_minutes=24,
        status=EnrollmentStepStatus.PENDING,
        meta_template_name="t",
        message_text=None,
        template_variables={},
        scheduled_job_id=uuid.uuid4(),
    )
    use_case, enrollment, enrollment_repo, _, sched_repo = _make_use_case([], [enr_step])
    audit = await use_case.execute(
        enrollment_id=enrollment.id, flow_id=uuid.uuid4(), account_id=uuid.uuid4()
    )
    assert audit["steps_cancelled"] == 1
    sched_repo.cancel.assert_awaited_with(enr_step.scheduled_job_id)
    enrollment_repo.cancel_step.assert_awaited_with(enr_step.id)


@pytest.mark.asyncio
async def test_resync_idempotent_on_unchanged_state():
    fs_id = uuid.uuid4()
    flow_steps = [
        SimpleNamespace(
            id=fs_id,
            position=1,
            delay_from_previous_minutes=24,
            meta_template_name="t",
            message_text=None,
            template_variables={},
        )
    ]
    enr_step = SimpleNamespace(
        id=uuid.uuid4(),
        flow_step_id=fs_id,
        position=1,
        delay_from_previous_minutes=24,
        status=EnrollmentStepStatus.PENDING,
        meta_template_name="t",
        message_text=None,
        template_variables={},
        scheduled_job_id=uuid.uuid4(),
    )
    use_case, enrollment, *_ = _make_use_case(flow_steps, [enr_step])
    audit = await use_case.execute(
        enrollment_id=enrollment.id, flow_id=uuid.uuid4(), account_id=uuid.uuid4()
    )
    assert audit == {
        "steps_added": 0,
        "steps_rescheduled": 0,
        "steps_content_updated": 0,
        "steps_cancelled": 0,
    }
