from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from shared.application.use_cases.followup.dispatch_followup_step import DispatchFollowupStep
from shared.domain.entities.followup import EnrollmentStepStatus, FollowupEnrollmentStep


def _make_step(
    status: EnrollmentStepStatus = EnrollmentStepStatus.PENDING,
) -> FollowupEnrollmentStep:
    return FollowupEnrollmentStep(
        id=uuid4(),
        enrollment_id=uuid4(),
        position=1,
        delay_from_purchase_hours=0,
        meta_template_name="mv_boas_vindas",
        template_variables={"nome": "{{1}}"},
        scheduled_job_id=uuid4(),
        status=status,
    )


@pytest.mark.asyncio
async def test_dispatch_sends_template_and_saves_to_history():
    step = _make_step()
    enrollment_repo = AsyncMock()
    enrollment_repo.find_step_by_id.return_value = step
    enrollment_repo.all_steps_sent.return_value = False

    chatnexo = AsyncMock()
    history = AsyncMock()
    history.load.return_value = [{"role": "user", "content": "oi"}]

    account_id = uuid4()
    conversation_id = uuid4()
    contact_phone = "5511999990000"
    thread_id = f"{account_id}:{contact_phone}"

    uc = DispatchFollowupStep(
        enrollment_repo=enrollment_repo, chatnexo=chatnexo, conversation_history=history
    )
    result = await uc.execute(
        enrollment_step_id=step.id,
        account_id=account_id,
        conversation_id=conversation_id,
        contact_phone=contact_phone,
    )

    assert result == "SENT"
    chatnexo.send_template.assert_called_once_with(
        account_id=str(account_id),
        conversation_id=str(conversation_id),
        template_name="mv_boas_vindas",
        variables={"nome": "{{1}}"},
    )
    history.load.assert_called_once_with(thread_id=thread_id)
    history.save.assert_called_once()
    saved_messages = history.save.call_args.kwargs["messages"]
    assert any(
        m.get("role") == "assistant" and "mv_boas_vindas" in m.get("content", "")
        for m in saved_messages
    )
    enrollment_repo.update_step.assert_called_once()
    updated_step: FollowupEnrollmentStep = enrollment_repo.update_step.call_args.args[0]
    assert updated_step.status == EnrollmentStepStatus.SENT
    assert updated_step.sent_at is not None


@pytest.mark.asyncio
async def test_dispatch_marks_enrollment_completed_when_all_steps_sent():
    step = _make_step()
    enrollment_repo = AsyncMock()
    enrollment_repo.find_step_by_id.return_value = step
    enrollment_repo.all_steps_sent.return_value = True

    uc = DispatchFollowupStep(
        enrollment_repo=enrollment_repo,
        chatnexo=AsyncMock(),
        conversation_history=AsyncMock(load=AsyncMock(return_value=[])),
    )
    await uc.execute(
        enrollment_step_id=step.id,
        account_id=uuid4(),
        conversation_id=uuid4(),
        contact_phone="5511999990000",
    )

    from shared.domain.entities.followup import EnrollmentStatus

    enrollment_repo.update_enrollment_status.assert_called_once_with(
        step.enrollment_id, EnrollmentStatus.COMPLETED
    )


@pytest.mark.asyncio
async def test_dispatch_ignores_already_sent_step():
    step = _make_step(status=EnrollmentStepStatus.SENT)
    enrollment_repo = AsyncMock()
    enrollment_repo.find_step_by_id.return_value = step

    uc = DispatchFollowupStep(
        enrollment_repo=enrollment_repo,
        chatnexo=AsyncMock(),
        conversation_history=AsyncMock(),
    )
    result = await uc.execute(
        enrollment_step_id=step.id,
        account_id=uuid4(),
        conversation_id=uuid4(),
        contact_phone="5511999990000",
    )
    assert result == "IGNORADO"
    enrollment_repo.update_step.assert_not_called()
