from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from shared.application.use_cases.onboarding.dispatch_onboarding_step import (
    DispatchOnboardingStep,
    DispatchResult,
)
from shared.domain.entities.onboarding import EnrollmentStepStatus


def _step(status=EnrollmentStepStatus.PENDING, template="t", text=None):
    return SimpleNamespace(
        id=uuid.uuid4(),
        enrollment_id=uuid.uuid4(),
        status=status,
        meta_template_name=template,
        message_text=text,
        template_variables={},
    )


@pytest.mark.asyncio
async def test_dispatch_marks_failed_on_send_template_error():
    """Exceção em send_template → step FAILED + failure_reason salvo."""
    step = _step()
    enrollment_repo = AsyncMock()
    enrollment_repo.find_step_by_id.return_value = step
    enrollment_repo.find_enrollment_by_id.return_value = SimpleNamespace(
        customer_name="X",
        product_name="P",
        contact_phone="+5511",
        contact_id=uuid.uuid4(),
    )

    chatnexo = AsyncMock()
    chatnexo.send_template.side_effect = RuntimeError("ChatNexo 500")

    template_repo = AsyncMock()
    template_repo.get_by_name.return_value = None

    use_case = DispatchOnboardingStep(
        enrollment_repo=enrollment_repo,
        contact_repo=AsyncMock(),
        chatnexo=chatnexo,
        conversation_history=AsyncMock(),
        meta_template_repo=template_repo,
    )

    result = await use_case.execute(
        enrollment_step_id=step.id,
        account_id=uuid.uuid4(),
        conversation_id="c",
        contact_phone="+5511",
    )

    assert isinstance(result, DispatchResult)
    assert result.status == EnrollmentStepStatus.FAILED
    assert "ChatNexo 500" in result.failure_reason
    enrollment_repo.mark_failed.assert_awaited_once()
    args, _ = enrollment_repo.mark_failed.call_args
    assert args[0] == step.id
    assert "ChatNexo 500" in args[1]


@pytest.mark.asyncio
async def test_dispatch_marks_failed_on_send_message_error():
    """Exceção em send_message (texto livre) → step FAILED."""
    step = _step(template=None, text="oi")
    enrollment_repo = AsyncMock()
    enrollment_repo.find_step_by_id.return_value = step

    chatnexo = AsyncMock()
    chatnexo.send_message.side_effect = ValueError("api down")

    use_case = DispatchOnboardingStep(
        enrollment_repo=enrollment_repo,
        contact_repo=AsyncMock(),
        chatnexo=chatnexo,
        conversation_history=AsyncMock(),
        meta_template_repo=AsyncMock(),
    )

    result = await use_case.execute(
        enrollment_step_id=step.id,
        account_id=uuid.uuid4(),
        conversation_id="c",
        contact_phone="+5511",
    )

    assert result.status == EnrollmentStepStatus.FAILED
    assert "api down" in result.failure_reason


@pytest.mark.asyncio
async def test_dispatch_returns_sent_on_success():
    """Caminho feliz: retorna DispatchResult.status=SENT, sem failure_reason."""
    step = _step()
    enrollment_repo = AsyncMock()
    enrollment_repo.find_step_by_id.return_value = step
    enrollment_repo.find_enrollment_by_id.return_value = SimpleNamespace(
        customer_name="X",
        product_name="P",
        contact_phone="+5511",
        contact_id=uuid.uuid4(),
    )
    enrollment_repo.all_steps_sent.return_value = False

    chatnexo = AsyncMock()
    template_repo = AsyncMock()
    template_repo.get_by_name.return_value = None
    history = AsyncMock()
    history.load.return_value = []

    use_case = DispatchOnboardingStep(
        enrollment_repo=enrollment_repo,
        contact_repo=AsyncMock(),
        chatnexo=chatnexo,
        conversation_history=history,
        meta_template_repo=template_repo,
    )

    result = await use_case.execute(
        enrollment_step_id=step.id,
        account_id=uuid.uuid4(),
        conversation_id="c",
        contact_phone="+5511",
    )

    assert result.status == EnrollmentStepStatus.SENT
    assert result.failure_reason is None
