from __future__ import annotations

"""
Testa que o DispatchFollowupStep passa corretamente header_link e header_kind
para chatnexo.send_template quando o step tem mídia associada (via getattr).

Nota: FollowupEnrollmentStep atual não possui media_url/media_kind — esses campos
são acessados via getattr com default None, deixando o código preparado para
evolução futura da entidade sem quebrar o comportamento atual.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from shared.application.use_cases.followup.dispatch_followup_step import DispatchFollowupStep
from shared.domain.entities.followup import EnrollmentStepStatus, FollowupEnrollmentStep


def _make_step_entity(
    status: EnrollmentStepStatus = EnrollmentStepStatus.PENDING,
) -> FollowupEnrollmentStep:
    """Cria FollowupEnrollmentStep real (sem media_url/media_kind)."""
    return FollowupEnrollmentStep(
        id=uuid4(),
        enrollment_id=uuid4(),
        position=1,
        delay_from_purchase_hours=0,
        meta_template_name="promo_video",
        template_variables={"nome": "João"},
        status=status,
    )


def _make_step_with_media() -> SimpleNamespace:
    """
    Simula um step com campos media_url e media_kind (para futuras versões
    da entidade). Usa SimpleNamespace pois FollowupEnrollmentStep (slots=True)
    não aceita atributos extras.
    """
    return SimpleNamespace(
        id=uuid4(),
        enrollment_id=uuid4(),
        position=1,
        delay_from_purchase_hours=0,
        meta_template_name="promo_video",
        template_variables={"nome": "João"},
        message_text=None,
        status=EnrollmentStepStatus.PENDING,
        sent_at=None,
        scheduled_job_id=None,
        # campos de mídia — presentes em versões futuras da entidade
        media_url="https://media.example.com/video.mp4",
        media_kind="video",
        language="pt_BR",
    )


@pytest.mark.asyncio
async def test_dispatch_template_step_without_media_passes_none_header():
    """Step sem media_url → send_template chamado com header_link=None e header_kind=None."""
    step = _make_step_entity()
    enrollment_repo = AsyncMock()
    enrollment_repo.find_step_by_id.return_value = step
    enrollment_repo.all_steps_sent.return_value = False

    chatnexo = AsyncMock()
    history = AsyncMock()
    history.load.return_value = []

    account_id = uuid4()
    conversation_id = uuid4()

    uc = DispatchFollowupStep(
        enrollment_repo=enrollment_repo, chatnexo=chatnexo, conversation_history=history
    )
    result = await uc.execute(
        enrollment_step_id=step.id,
        account_id=account_id,
        conversation_id=str(conversation_id),
        contact_phone="5511999990000",
    )

    assert result == "SENT"
    call_kwargs = chatnexo.send_template.call_args.kwargs
    assert call_kwargs["header_link"] is None
    assert call_kwargs["header_kind"] is None
    assert call_kwargs["language"] is None
    assert call_kwargs["template_name"] == "promo_video"


@pytest.mark.asyncio
async def test_dispatch_template_step_with_media_passes_header_kwargs():
    """Step com media_url e media_kind → send_template chamado com header_link e header_kind corretos."""
    step = _make_step_with_media()
    enrollment_repo = AsyncMock()
    enrollment_repo.find_step_by_id.return_value = step
    enrollment_repo.all_steps_sent.return_value = False

    chatnexo = AsyncMock()
    history = AsyncMock()
    history.load.return_value = []

    account_id = uuid4()
    conversation_id = uuid4()

    uc = DispatchFollowupStep(
        enrollment_repo=enrollment_repo, chatnexo=chatnexo, conversation_history=history
    )
    result = await uc.execute(
        enrollment_step_id=step.id,
        account_id=account_id,
        conversation_id=str(conversation_id),
        contact_phone="5511999990000",
    )

    assert result == "SENT"
    call_kwargs = chatnexo.send_template.call_args.kwargs
    assert call_kwargs["header_link"] == "https://media.example.com/video.mp4"
    assert call_kwargs["header_kind"] == "video"
    assert call_kwargs["language"] == "pt_BR"
    assert call_kwargs["template_name"] == "promo_video"
