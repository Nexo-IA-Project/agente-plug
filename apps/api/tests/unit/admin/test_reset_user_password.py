from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from shared.application.use_cases.admin.reset_user_password import ResetUserPasswordUseCase


@pytest.mark.asyncio
async def test_reset_password_updates_hash_and_sends_email():
    existing = MagicMock()
    existing.id = "id-1"
    existing.name = "Pedro"
    existing.email = "pedro@example.com"

    mock_repo = MagicMock()
    mock_repo.get_by_id = AsyncMock(return_value=existing)
    mock_repo.update_password = AsyncMock()
    mock_email = MagicMock()
    mock_email.send_email = AsyncMock()

    uc = ResetUserPasswordUseCase(identity_repo=mock_repo, email_service=mock_email)
    await uc.execute(account_id=uuid.uuid4(), identity_id="id-1")

    mock_repo.update_password.assert_awaited_once()
    kwargs = mock_repo.update_password.await_args.kwargs
    assert kwargs["identity_id"] == "id-1"
    assert kwargs["must_change_password"] is True
    assert kwargs["new_hash"] != ""

    mock_email.send_email.assert_awaited_once()
    call = mock_email.send_email.await_args
    assert call.kwargs["to"] == "pedro@example.com"


@pytest.mark.asyncio
async def test_reset_password_raises_when_identity_not_found():
    mock_repo = MagicMock()
    mock_repo.get_by_id = AsyncMock(return_value=None)

    uc = ResetUserPasswordUseCase(identity_repo=mock_repo, email_service=MagicMock())
    with pytest.raises(LookupError):
        await uc.execute(account_id=uuid.uuid4(), identity_id="missing")
