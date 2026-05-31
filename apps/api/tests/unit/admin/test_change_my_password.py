from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from shared.adapters.kb.jwt_handler import hash_password
from shared.application.use_cases.admin.change_my_password import (
    ChangeMyPasswordUseCase,
    InvalidCurrentPasswordError,
)


@pytest.mark.asyncio
async def test_change_password_succeeds_when_current_matches():
    user = MagicMock()
    user.id = "uid"
    user.password_hash = hash_password("current123")

    mock_repo = MagicMock()
    mock_repo.get_by_id = AsyncMock(return_value=user)
    mock_repo.update_password = AsyncMock()

    uc = ChangeMyPasswordUseCase(identity_repo=mock_repo)
    await uc.execute(identity_id="uid", current_password="current123", new_password="newPass!9")

    mock_repo.update_password.assert_awaited_once()
    kwargs = mock_repo.update_password.await_args.kwargs
    assert kwargs["must_change_password"] is False


@pytest.mark.asyncio
async def test_change_password_rejects_wrong_current():
    user = MagicMock()
    user.password_hash = hash_password("real")

    mock_repo = MagicMock()
    mock_repo.get_by_id = AsyncMock(return_value=user)
    mock_repo.update_password = AsyncMock()

    uc = ChangeMyPasswordUseCase(identity_repo=mock_repo)
    with pytest.raises(InvalidCurrentPasswordError):
        await uc.execute(identity_id="uid", current_password="wrong", new_password="newPass!9")
    mock_repo.update_password.assert_not_awaited()


@pytest.mark.asyncio
async def test_change_password_validates_new_min_length():
    user = MagicMock()
    user.password_hash = hash_password("ok")

    mock_repo = MagicMock()
    mock_repo.get_by_id = AsyncMock(return_value=user)

    uc = ChangeMyPasswordUseCase(identity_repo=mock_repo)
    with pytest.raises(ValueError, match="at least 8"):
        await uc.execute(identity_id="uid", current_password="ok", new_password="short")
