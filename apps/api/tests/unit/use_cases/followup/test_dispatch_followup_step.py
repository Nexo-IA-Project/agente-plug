from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from shared.application.use_cases.onboarding.dispatch_onboarding_step import (
    DispatchOnboardingStep,
    DispatchResult,
)
from shared.domain.entities.onboarding import EnrollmentStepStatus, OnboardingEnrollmentStep


def _make_step(
    status: EnrollmentStepStatus = EnrollmentStepStatus.PENDING,
    template_variables: dict | None = None,
) -> OnboardingEnrollmentStep:
    return OnboardingEnrollmentStep(
        id=uuid4(),
        enrollment_id=uuid4(),
        position=1,
        delay_from_purchase_minutes=0,
        meta_template_name="mv_boas_vindas",
        template_variables=(
            template_variables
            if template_variables is not None
            else {"1": {"source": "static", "value": "Fabio"}}
        ),
        scheduled_job_id=uuid4(),
        status=status,
    )


def _make_enrollment_repo_with_step(
    step: OnboardingEnrollmentStep,
    *,
    enrollment: SimpleNamespace | None = None,
    all_steps_sent: bool = False,
) -> AsyncMock:
    enrollment_repo = AsyncMock()
    enrollment_repo.find_step_by_id.return_value = step
    enrollment_repo.all_steps_sent.return_value = all_steps_sent
    if enrollment is None:
        enrollment = SimpleNamespace(
            id=step.enrollment_id,
            contact_id=uuid4(),
            customer_name="Fabio",
            product_name="Marketing 360",
            contact_phone="+5511999990000",
        )
    enrollment_repo.find_enrollment_by_id.return_value = enrollment
    return enrollment_repo


def _make_contact_repo(email: str | None = "fabio@example.com") -> AsyncMock:
    contact_repo = AsyncMock()
    contact_repo.find_by_id.return_value = SimpleNamespace(email=email)
    return contact_repo


@pytest.mark.asyncio
async def test_dispatch_sends_template_and_saves_to_history():
    step = _make_step(template_variables={"1": {"source": "static", "value": "Fabio"}})
    enrollment_repo = _make_enrollment_repo_with_step(step)

    chatnexo = AsyncMock()
    history = AsyncMock()
    history.load.return_value = [{"role": "user", "content": "oi"}]

    account_id = uuid4()
    conversation_id = uuid4()
    contact_phone = "5511999990000"
    thread_id = f"{account_id}:{contact_phone}"

    uc = DispatchOnboardingStep(
        enrollment_repo=enrollment_repo,
        contact_repo=_make_contact_repo(),
        chatnexo=chatnexo,
        conversation_history=history,
        meta_template_repo=AsyncMock(get_by_name=AsyncMock(return_value=None)),
    )
    result = await uc.execute(
        enrollment_step_id=step.id,
        account_id=account_id,
        conversation_id=conversation_id,
        contact_phone=contact_phone,
    )

    assert isinstance(result, DispatchResult)
    assert result.status == EnrollmentStepStatus.SENT
    # account_id passado pro ChatNexo é o chatnexo_account_id (int) — Chatwoot
    # fork usa integer, não o UUID local. rendered_body=None porque o template
    # mockado não tem body components.
    chatnexo.send_template.assert_called_once_with(
        account_id="1",
        conversation_id=str(conversation_id),
        template_name="mv_boas_vindas",
        language=None,
        variables={"1": "Fabio"},
        header_link=None,
        header_kind=None,
        rendered_body=None,
        parameter_format="NAMED",
    )
    history.load.assert_called_once_with(thread_id=thread_id)
    history.save.assert_called_once()
    saved_messages = history.save.call_args.kwargs["messages"]
    assert any(
        m.get("role") == "assistant" and "mv_boas_vindas" in m.get("content", "")
        for m in saved_messages
    )
    enrollment_repo.update_step.assert_called_once()
    updated_step: OnboardingEnrollmentStep = enrollment_repo.update_step.call_args.args[0]
    assert updated_step.status == EnrollmentStepStatus.SENT
    assert updated_step.sent_at is not None


@pytest.mark.asyncio
async def test_dispatch_marks_enrollment_completed_when_all_steps_sent():
    step = _make_step()
    enrollment_repo = _make_enrollment_repo_with_step(step, all_steps_sent=True)

    uc = DispatchOnboardingStep(
        enrollment_repo=enrollment_repo,
        contact_repo=_make_contact_repo(),
        chatnexo=AsyncMock(),
        conversation_history=AsyncMock(load=AsyncMock(return_value=[])),
        meta_template_repo=AsyncMock(get_by_name=AsyncMock(return_value=None)),
    )
    await uc.execute(
        enrollment_step_id=step.id,
        account_id=uuid4(),
        conversation_id=uuid4(),
        contact_phone="5511999990000",
    )

    from shared.domain.entities.onboarding import EnrollmentStatus

    enrollment_repo.update_enrollment_status.assert_called_once_with(
        step.enrollment_id, EnrollmentStatus.COMPLETED
    )


@pytest.mark.asyncio
async def test_dispatch_ignores_already_sent_step():
    step = _make_step(status=EnrollmentStepStatus.SENT)
    enrollment_repo = _make_enrollment_repo_with_step(step)

    uc = DispatchOnboardingStep(
        enrollment_repo=enrollment_repo,
        contact_repo=_make_contact_repo(),
        chatnexo=AsyncMock(),
        conversation_history=AsyncMock(),
        meta_template_repo=AsyncMock(get_by_name=AsyncMock(return_value=None)),
    )
    result = await uc.execute(
        enrollment_step_id=step.id,
        account_id=uuid4(),
        conversation_id=uuid4(),
        contact_phone="5511999990000",
    )
    assert isinstance(result, DispatchResult)
    assert result.label == "IGNORADO"
    assert result.status == EnrollmentStepStatus.SENT
    enrollment_repo.update_step.assert_not_called()


@pytest.mark.asyncio
async def test_dispatch_resolves_dynamic_variables():
    """Step com bindings dinâmicos resolve customer_name e product_name do enrollment."""
    enrollment_id = uuid4()
    contact_id = uuid4()
    step = OnboardingEnrollmentStep(
        id=uuid4(),
        enrollment_id=enrollment_id,
        position=0,
        delay_from_purchase_minutes=0,
        meta_template_name="welcome",
        template_variables={
            "1": {"source": "customer_name"},
            "2": {"source": "product_name"},
        },
        status=EnrollmentStepStatus.PENDING,
    )
    enrollment = SimpleNamespace(
        id=enrollment_id,
        contact_id=contact_id,
        customer_name="Fabio",
        product_name="Marketing 360",
        contact_phone="+5511",
    )
    enrollment_repo = _make_enrollment_repo_with_step(step, enrollment=enrollment)
    contact_repo = _make_contact_repo(email="fabio@example.com")
    chatnexo = AsyncMock()
    template_repo = AsyncMock()
    template_repo.get_by_name.return_value = SimpleNamespace(
        media_url=None, media_kind=None, language="pt_BR"
    )

    uc = DispatchOnboardingStep(
        enrollment_repo=enrollment_repo,
        contact_repo=contact_repo,
        chatnexo=chatnexo,
        conversation_history=AsyncMock(load=AsyncMock(return_value=[])),
        meta_template_repo=template_repo,
    )
    await uc.execute(
        enrollment_step_id=step.id,
        account_id=uuid4(),
        conversation_id="conv1",
        contact_phone="+5511",
    )

    sent_kwargs = chatnexo.send_template.call_args.kwargs
    assert sent_kwargs["variables"] == {"1": "Fabio", "2": "Marketing 360"}
    contact_repo.find_by_id.assert_called_once_with(contact_id)


@pytest.mark.asyncio
async def test_dispatch_detects_positional_from_body_text():
    """Template sem `example` mas com {{1}} no body → POSITIONAL via fallback."""
    step = _make_step(template_variables={"1": {"source": "static", "value": "Fabio"}})
    enrollment_repo = _make_enrollment_repo_with_step(step)
    chatnexo = AsyncMock()
    template_repo = AsyncMock()
    template_repo.get_by_name.return_value = SimpleNamespace(
        media_url=None,
        media_kind=None,
        language="pt_BR",
        components=[{"type": "BODY", "text": "Olá {{1}}, tudo bem?"}],
    )

    uc = DispatchOnboardingStep(
        enrollment_repo=enrollment_repo,
        contact_repo=_make_contact_repo(),
        chatnexo=chatnexo,
        conversation_history=AsyncMock(load=AsyncMock(return_value=[])),
        meta_template_repo=template_repo,
    )
    await uc.execute(
        enrollment_step_id=step.id,
        account_id=uuid4(),
        conversation_id="conv1",
        contact_phone="+5511",
    )

    sent_kwargs = chatnexo.send_template.call_args.kwargs
    assert sent_kwargs["parameter_format"] == "POSITIONAL"


@pytest.mark.asyncio
async def test_dispatch_detects_named_from_body_text():
    """Template sem `example` mas com {{customer_name}} no body → NAMED via fallback."""
    step = _make_step(
        template_variables={"customer_name": {"source": "static", "value": "Fabio"}}
    )
    enrollment_repo = _make_enrollment_repo_with_step(step)
    chatnexo = AsyncMock()
    template_repo = AsyncMock()
    template_repo.get_by_name.return_value = SimpleNamespace(
        media_url=None,
        media_kind=None,
        language="pt_BR",
        components=[{"type": "BODY", "text": "Olá {{customer_name}}, bem-vindo!"}],
    )

    uc = DispatchOnboardingStep(
        enrollment_repo=enrollment_repo,
        contact_repo=_make_contact_repo(),
        chatnexo=chatnexo,
        conversation_history=AsyncMock(load=AsyncMock(return_value=[])),
        meta_template_repo=template_repo,
    )
    await uc.execute(
        enrollment_step_id=step.id,
        account_id=uuid4(),
        conversation_id="conv1",
        contact_phone="+5511",
    )

    sent_kwargs = chatnexo.send_template.call_args.kwargs
    assert sent_kwargs["parameter_format"] == "NAMED"


@pytest.mark.asyncio
async def test_dispatch_resolves_static_binding():
    """Step com binding static usa o `value` literal."""
    step = _make_step(template_variables={"1": {"source": "static", "value": "Promo Black Friday"}})
    enrollment_repo = _make_enrollment_repo_with_step(step)
    chatnexo = AsyncMock()

    uc = DispatchOnboardingStep(
        enrollment_repo=enrollment_repo,
        contact_repo=_make_contact_repo(),
        chatnexo=chatnexo,
        conversation_history=AsyncMock(load=AsyncMock(return_value=[])),
        meta_template_repo=AsyncMock(get_by_name=AsyncMock(return_value=None)),
    )
    await uc.execute(
        enrollment_step_id=step.id,
        account_id=uuid4(),
        conversation_id=str(uuid4()),
        contact_phone="5511999990000",
    )

    sent_kwargs = chatnexo.send_template.call_args.kwargs
    assert sent_kwargs["variables"] == {"1": "Promo Black Friday"}
