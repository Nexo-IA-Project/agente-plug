from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from shared.application.use_cases.admin.create_user import CreateUserUseCase
from shared.domain.entities.user import UserRole


@pytest.mark.asyncio
async def test_create_user_generates_password_and_sends_email():
    mock_repo = MagicMock()
    mock_repo.get_by_email = AsyncMock(return_value=None)
    mock_repo.save = AsyncMock()
    mock_email = MagicMock()
    mock_email.send_email = AsyncMock()

    uc = CreateUserUseCase(user_repo=mock_repo, email_service=mock_email)

    user = await uc.execute(
        account_id=1,
        name="Joana",
        email="joana@example.com",
        role=UserRole.OPERATOR,
    )

    assert user.name == "Joana"
    assert user.role == UserRole.OPERATOR
    assert user.must_change_password is True
    assert user.password_hash != ""
    mock_repo.save.assert_awaited_once()
    mock_email.send_email.assert_awaited_once()
    call = mock_email.send_email.await_args
    assert call.kwargs["to"] == "joana@example.com"
    assert "Joana" in call.kwargs["body_html"]


@pytest.mark.asyncio
async def test_create_user_rejects_duplicate_email():
    existing = MagicMock()
    mock_repo = MagicMock()
    mock_repo.get_by_email = AsyncMock(return_value=existing)

    uc = CreateUserUseCase(user_repo=mock_repo, email_service=MagicMock())

    with pytest.raises(ValueError, match="already exists"):
        await uc.execute(account_id=1, name="X", email="dup@x.com", role=UserRole.ADMIN)
