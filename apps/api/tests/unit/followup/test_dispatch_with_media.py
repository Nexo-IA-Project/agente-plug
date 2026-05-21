"""Testa que o DispatchFollowupStep passa corretamente header_link e header_kind
para chatnexo.send_template quando o template associado ao step tem mídia.

A mídia é lida do MetaTemplateModel via MetaTemplateRepository.get_by_name,
não do FollowupEnrollmentStep (que não possui esses campos).
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from shared.adapters.db.models import MetaTemplateModel
from shared.application.use_cases.followup.dispatch_followup_step import DispatchFollowupStep
from shared.domain.entities.followup import EnrollmentStepStatus, FollowupEnrollmentStep


def _make_step(
    status: EnrollmentStepStatus = EnrollmentStepStatus.PENDING,
    meta_template_name: str = "promo_video",
) -> FollowupEnrollmentStep:
    """Cria FollowupEnrollmentStep real (entidade de domínio)."""
    return FollowupEnrollmentStep(
        id=uuid4(),
        enrollment_id=uuid4(),
        position=1,
        delay_from_purchase_hours=0,
        meta_template_name=meta_template_name,
        template_variables={"1": {"source": "static", "value": "João"}},
        status=status,
    )


def _make_template(
    *,
    media_url: str | None = None,
    media_kind: str | None = None,
    language: str = "pt_BR",
) -> MagicMock:
    """Cria mock de MetaTemplateModel com os campos relevantes."""
    tmpl = MagicMock(spec=MetaTemplateModel)
    tmpl.media_url = media_url
    tmpl.media_kind = media_kind
    tmpl.language = language
    return tmpl


def _make_uc(
    *, step, template_return_value
) -> tuple[DispatchFollowupStep, AsyncMock, AsyncMock, AsyncMock]:
    enrollment_repo = AsyncMock()
    enrollment_repo.find_step_by_id.return_value = step
    enrollment_repo.all_steps_sent.return_value = False
    enrollment_repo.find_enrollment_by_id.return_value = SimpleNamespace(
        id=step.enrollment_id,
        contact_id=uuid4(),
        customer_name="João",
        product_name="Promo",
        contact_phone="+5511999990000",
    )

    contact_repo = AsyncMock()
    contact_repo.find_by_id.return_value = SimpleNamespace(email="joao@example.com")

    chatnexo = AsyncMock()
    history = AsyncMock()
    history.load.return_value = []

    template_repo = AsyncMock()
    template_repo.get_by_name.return_value = template_return_value

    uc = DispatchFollowupStep(
        enrollment_repo=enrollment_repo,
        contact_repo=contact_repo,
        chatnexo=chatnexo,
        conversation_history=history,
        meta_template_repo=template_repo,
    )
    return uc, chatnexo, enrollment_repo, template_repo


@pytest.mark.asyncio
async def test_dispatch_template_step_with_image_media():
    """Template com media_url e media_kind=IMAGE → header_link correto + header_kind em lowercase."""
    step = _make_step()
    template = _make_template(
        media_url="https://media.example.com/image.jpg",
        media_kind="IMAGE",
        language="pt_BR",
    )
    uc, chatnexo, _, template_repo = _make_uc(step=step, template_return_value=template)

    account_id = uuid4()
    result = await uc.execute(
        enrollment_step_id=step.id,
        account_id=account_id,
        conversation_id=str(uuid4()),
        contact_phone="5511999990000",
    )

    assert result == "SENT"
    template_repo.get_by_name.assert_called_once_with(name="promo_video", account_id=account_id)
    call_kwargs = chatnexo.send_template.call_args.kwargs
    assert call_kwargs["header_link"] == "https://media.example.com/image.jpg"
    assert call_kwargs["header_kind"] == "image"  # lowercase
    assert call_kwargs["language"] == "pt_BR"
    assert call_kwargs["template_name"] == "promo_video"


@pytest.mark.asyncio
async def test_dispatch_template_step_with_video_media():
    """Template com media_url e media_kind=VIDEO → header_kind=video (lowercase)."""
    step = _make_step()
    template = _make_template(
        media_url="https://media.example.com/video.mp4",
        media_kind="VIDEO",
        language="pt_BR",
    )
    uc, chatnexo, _, _ = _make_uc(step=step, template_return_value=template)

    result = await uc.execute(
        enrollment_step_id=step.id,
        account_id=uuid4(),
        conversation_id=str(uuid4()),
        contact_phone="5511999990000",
    )

    assert result == "SENT"
    call_kwargs = chatnexo.send_template.call_args.kwargs
    assert call_kwargs["header_link"] == "https://media.example.com/video.mp4"
    assert call_kwargs["header_kind"] == "video"


@pytest.mark.asyncio
async def test_dispatch_template_step_without_media_passes_none_header():
    """Template sem media_url → send_template chamado com header_link=None e header_kind=None."""
    step = _make_step()
    template = _make_template(media_url=None, media_kind=None, language="pt_BR")
    uc, chatnexo, _, _ = _make_uc(step=step, template_return_value=template)

    result = await uc.execute(
        enrollment_step_id=step.id,
        account_id=uuid4(),
        conversation_id=str(uuid4()),
        contact_phone="5511999990000",
    )

    assert result == "SENT"
    call_kwargs = chatnexo.send_template.call_args.kwargs
    assert call_kwargs["header_link"] is None
    assert call_kwargs["header_kind"] is None
    assert call_kwargs["language"] == "pt_BR"
    assert call_kwargs["template_name"] == "promo_video"


@pytest.mark.asyncio
async def test_dispatch_template_step_template_not_found_still_works():
    """Quando get_by_name retorna None (template não cadastrado localmente), dispatch ainda funciona sem header."""
    step = _make_step()
    uc, chatnexo, _, template_repo = _make_uc(step=step, template_return_value=None)

    account_id = uuid4()
    result = await uc.execute(
        enrollment_step_id=step.id,
        account_id=account_id,
        conversation_id=str(uuid4()),
        contact_phone="5511999990000",
    )

    assert result == "SENT"
    template_repo.get_by_name.assert_called_once_with(name="promo_video", account_id=account_id)
    call_kwargs = chatnexo.send_template.call_args.kwargs
    assert call_kwargs["header_link"] is None
    assert call_kwargs["header_kind"] is None
    assert call_kwargs["language"] is None
    assert call_kwargs["template_name"] == "promo_video"
