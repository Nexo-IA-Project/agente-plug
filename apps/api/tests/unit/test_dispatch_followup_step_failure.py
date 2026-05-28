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


@pytest.mark.asyncio
async def test_publishes_enrollment_updated_on_success():
    """Task 15: ao despachar com sucesso, publica `lead.enrollment.updated`
    no LeadsPubSub com step_status=sent."""
    step = _step()
    enrollment_id = uuid.uuid4()
    step.enrollment_id = enrollment_id
    contact_id = uuid.uuid4()
    account_id = uuid.uuid4()

    enrollment = SimpleNamespace(
        id=enrollment_id,
        account_id=account_id,
        customer_name="X",
        product_name="P",
        contact_phone="+5511",
        contact_id=contact_id,
        status=SimpleNamespace(value="active"),
        flow_id=None,
    )

    enrollment_repo = AsyncMock()
    enrollment_repo.find_step_by_id.return_value = step
    enrollment_repo.find_enrollment_by_id.return_value = enrollment
    enrollment_repo.all_steps_sent.return_value = False

    chatnexo = AsyncMock()
    template_repo = AsyncMock()
    template_repo.get_by_name.return_value = None
    history = AsyncMock()
    history.load.return_value = []

    leads_pubsub = AsyncMock()
    leads_pubsub.publish = AsyncMock()

    # Session=None pula o lookup de lead_id (que viraria None de qualquer forma).
    use_case = DispatchOnboardingStep(
        enrollment_repo=enrollment_repo,
        contact_repo=AsyncMock(),
        chatnexo=chatnexo,
        conversation_history=history,
        meta_template_repo=template_repo,
        leads_pubsub=leads_pubsub,
        session=None,
    )

    result = await use_case.execute(
        enrollment_step_id=step.id,
        account_id=account_id,
        conversation_id="c",
        contact_phone="+5511",
    )

    assert result.status == EnrollmentStepStatus.SENT
    leads_pubsub.publish.assert_awaited_once()
    published_account, envelope = leads_pubsub.publish.await_args.args
    assert published_account == account_id
    assert envelope["type"] == "lead.enrollment.updated"
    assert envelope["lead_id"] is None  # sem session, lookup é skipped
    assert envelope["enrollment"]["id"] == str(enrollment_id)
    assert envelope["enrollment"]["step_id"] == str(step.id)
    assert envelope["enrollment"]["step_status"] == "sent"
    assert "template=" in envelope["enrollment"]["step_label"]


@pytest.mark.asyncio
async def test_publishes_enrollment_updated_on_template_failure():
    """Task 15: ao falhar envio de template, publica step_status='failed'."""
    step = _step()
    enrollment_id = uuid.uuid4()
    step.enrollment_id = enrollment_id
    account_id = uuid.uuid4()

    enrollment = SimpleNamespace(
        id=enrollment_id,
        account_id=account_id,
        customer_name="X",
        product_name="P",
        contact_phone="+5511",
        contact_id=uuid.uuid4(),
        status=SimpleNamespace(value="active"),
        flow_id=None,
    )

    enrollment_repo = AsyncMock()
    enrollment_repo.find_step_by_id.return_value = step
    enrollment_repo.find_enrollment_by_id.return_value = enrollment

    chatnexo = AsyncMock()
    chatnexo.send_template.side_effect = RuntimeError("boom")

    template_repo = AsyncMock()
    template_repo.get_by_name.return_value = None

    leads_pubsub = AsyncMock()
    leads_pubsub.publish = AsyncMock()

    use_case = DispatchOnboardingStep(
        enrollment_repo=enrollment_repo,
        contact_repo=AsyncMock(),
        chatnexo=chatnexo,
        conversation_history=AsyncMock(),
        meta_template_repo=template_repo,
        leads_pubsub=leads_pubsub,
        session=None,
    )

    result = await use_case.execute(
        enrollment_step_id=step.id,
        account_id=account_id,
        conversation_id="c",
        contact_phone="+5511",
    )

    assert result.status == EnrollmentStepStatus.FAILED
    leads_pubsub.publish.assert_awaited_once()
    _, envelope = leads_pubsub.publish.await_args.args
    assert envelope["type"] == "lead.enrollment.updated"
    assert envelope["enrollment"]["step_status"] == "failed"
    assert envelope["enrollment"]["step_label"] == "FAILED"


@pytest.mark.asyncio
async def test_publishes_enrollment_updated_on_message_text_failure():
    """Task 15: ao falhar envio de texto livre, publica step_status='failed'."""
    step = _step(template=None, text="oi")
    account_id = uuid.uuid4()

    enrollment = SimpleNamespace(
        id=uuid.uuid4(),
        account_id=account_id,
        contact_id=uuid.uuid4(),
        status=SimpleNamespace(value="active"),
        flow_id=None,
    )

    enrollment_repo = AsyncMock()
    enrollment_repo.find_step_by_id.return_value = step
    enrollment_repo.find_enrollment_by_id.return_value = enrollment

    chatnexo = AsyncMock()
    chatnexo.send_message.side_effect = ValueError("api down")

    leads_pubsub = AsyncMock()
    leads_pubsub.publish = AsyncMock()

    use_case = DispatchOnboardingStep(
        enrollment_repo=enrollment_repo,
        contact_repo=AsyncMock(),
        chatnexo=chatnexo,
        conversation_history=AsyncMock(),
        meta_template_repo=AsyncMock(),
        leads_pubsub=leads_pubsub,
        session=None,
    )

    result = await use_case.execute(
        enrollment_step_id=step.id,
        account_id=account_id,
        conversation_id="c",
        contact_phone="+5511",
    )

    assert result.status == EnrollmentStepStatus.FAILED
    leads_pubsub.publish.assert_awaited_once()
    _, envelope = leads_pubsub.publish.await_args.args
    assert envelope["enrollment"]["step_status"] == "failed"


@pytest.mark.asyncio
async def test_publishes_enrollment_updated_on_flow_inactive_cancel():
    """Task 15: quando flow está desativado, publica step_status='cancelled'."""
    step = _step()
    account_id = uuid.uuid4()
    flow_id = uuid.uuid4()

    enrollment = SimpleNamespace(
        id=uuid.uuid4(),
        account_id=account_id,
        contact_id=uuid.uuid4(),
        status=SimpleNamespace(value="active"),
        flow_id=flow_id,
    )

    enrollment_repo = AsyncMock()
    enrollment_repo.find_step_by_id.return_value = step
    enrollment_repo.find_enrollment_by_id.return_value = enrollment

    flow_repo = AsyncMock()
    flow_repo.find_by_id.return_value = SimpleNamespace(is_active=False)

    leads_pubsub = AsyncMock()
    leads_pubsub.publish = AsyncMock()

    use_case = DispatchOnboardingStep(
        enrollment_repo=enrollment_repo,
        contact_repo=AsyncMock(),
        chatnexo=AsyncMock(),
        conversation_history=AsyncMock(),
        meta_template_repo=AsyncMock(),
        flow_repo=flow_repo,
        leads_pubsub=leads_pubsub,
        session=None,
    )

    result = await use_case.execute(
        enrollment_step_id=step.id,
        account_id=account_id,
        conversation_id="c",
        contact_phone="+5511",
    )

    assert result.status == EnrollmentStepStatus.CANCELLED
    leads_pubsub.publish.assert_awaited_once()
    _, envelope = leads_pubsub.publish.await_args.args
    assert envelope["enrollment"]["step_status"] == "cancelled"
    assert "flow desativado" in envelope["enrollment"]["step_label"]


@pytest.mark.asyncio
async def test_does_not_publish_when_pubsub_absent():
    """Task 15: sem leads_pubsub injetado, não há crash e nada é publicado."""
    step = _step()
    enrollment_repo = AsyncMock()
    enrollment_repo.find_step_by_id.return_value = step
    enrollment_repo.find_enrollment_by_id.return_value = SimpleNamespace(
        id=uuid.uuid4(),
        account_id=uuid.uuid4(),
        customer_name="X",
        product_name="P",
        contact_phone="+5511",
        contact_id=uuid.uuid4(),
        status=SimpleNamespace(value="active"),
        flow_id=None,
    )
    enrollment_repo.all_steps_sent.return_value = False

    template_repo = AsyncMock()
    template_repo.get_by_name.return_value = None
    history = AsyncMock()
    history.load.return_value = []

    use_case = DispatchOnboardingStep(
        enrollment_repo=enrollment_repo,
        contact_repo=AsyncMock(),
        chatnexo=AsyncMock(),
        conversation_history=history,
        meta_template_repo=template_repo,
        # leads_pubsub NÃO é injetado
    )

    result = await use_case.execute(
        enrollment_step_id=step.id,
        account_id=uuid.uuid4(),
        conversation_id="c",
        contact_phone="+5511",
    )

    # Não deve crashar.
    assert result.status == EnrollmentStepStatus.SENT
