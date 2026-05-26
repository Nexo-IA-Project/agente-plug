from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


@pytest.mark.asyncio
async def test_handle_scheduled_followup_step_calls_dispatch():
    step_id = str(uuid4())
    account_id = str(uuid4())
    conv_id = "42"  # chatnexo external string, não UUID

    from shared.application.use_cases.onboarding.dispatch_onboarding_step import DispatchResult
    from shared.domain.entities.onboarding import EnrollmentStepStatus

    mock_dispatch = AsyncMock()
    mock_dispatch.execute = AsyncMock(
        return_value=DispatchResult(status=EnrollmentStepStatus.SENT, label="SENT")
    )

    mock_session = AsyncMock()

    @asynccontextmanager
    async def _fake_scope():
        yield mock_session

    with (
        patch("shared.adapters.db.session.session_scope", _fake_scope),
        patch(
            "shared.config.settings.get_settings",
            return_value=MagicMock(
                integration_credentials_key="Zm9vYmFyZm9vYmFyZm9vYmFyZm9vYmFyZm9vYmFyZm8="
            ),
        ),
        patch(
            "shared.adapters.db.repositories.account_config_repo.AccountConfigRepository"
        ) as mock_repo_cls,
        patch("shared.adapters.chatnexo.client.ChatNexoClient") as mock_chatnexo_cls,
        patch(
            "shared.adapters.db.repositories.onboarding_enrollment_repo.OnboardingEnrollmentRepository"
        ),
        patch("agent.history.ConversationHistory"),
        patch(
            "shared.application.use_cases.onboarding.dispatch_onboarding_step.DispatchOnboardingStep",
            return_value=mock_dispatch,
        ),
    ):
        mock_repo_instance = AsyncMock()
        mock_repo_instance.get = AsyncMock(return_value=MagicMock())
        mock_repo_cls.return_value = mock_repo_instance
        mock_chatnexo_cls.from_account_config = MagicMock(return_value=AsyncMock())

        from interface.worker.handlers.scheduled import handle_scheduled

        await handle_scheduled(
            {
                "job_type": "followup_step",
                "account_id": account_id,
                "conversation_id": conv_id,
                "contact_phone": "5511999990000",
                "enrollment_step_id": step_id,
            }
        )

    mock_dispatch.execute.assert_called_once()
    call_kwargs = mock_dispatch.execute.call_args.kwargs
    assert call_kwargs["conversation_id"] == conv_id  # str, não UUID
    assert call_kwargs["contact_phone"] == "5511999990000"
