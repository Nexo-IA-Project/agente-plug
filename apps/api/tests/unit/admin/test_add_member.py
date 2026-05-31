from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from shared.application.use_cases.admin.add_member import AddMemberUseCase
from shared.domain.entities.identity import Identity
from shared.domain.entities.user import UserRole


@pytest.mark.asyncio
async def test_new_email_creates_identity_and_sends_email():
    acc = uuid4()
    ident_repo = MagicMock(get_by_email=AsyncMock(return_value=None), save=AsyncMock())
    memb_repo = MagicMock(
        get_by_identity_and_account=AsyncMock(return_value=None), save=AsyncMock()
    )
    email_svc = MagicMock(send_email=AsyncMock())
    uc = AddMemberUseCase(
        identity_repo=ident_repo, membership_repo=memb_repo, email_service=email_svc
    )
    result = await uc.execute(
        account_id=acc, name="New", email="new@x.com", role=UserRole.OPERATOR, profile_id=None
    )
    assert result.created_identity is True
    ident_repo.save.assert_awaited_once()
    memb_repo.save.assert_awaited_once()
    email_svc.send_email.assert_awaited_once()


@pytest.mark.asyncio
async def test_existing_email_links_silently_no_new_password():
    acc = uuid4()
    existing = Identity(
        email="old@x.com", password_hash="keep", name="Old", must_change_password=False
    )
    ident_repo = MagicMock(get_by_email=AsyncMock(return_value=existing), save=AsyncMock())
    memb_repo = MagicMock(
        get_by_identity_and_account=AsyncMock(return_value=None), save=AsyncMock()
    )
    email_svc = MagicMock(send_email=AsyncMock())
    uc = AddMemberUseCase(
        identity_repo=ident_repo, membership_repo=memb_repo, email_service=email_svc
    )
    result = await uc.execute(
        account_id=acc, name="ignored", email="old@x.com", role=UserRole.ADMIN, profile_id=None
    )
    assert result.created_identity is False
    ident_repo.save.assert_not_awaited()
    memb_repo.save.assert_awaited_once()
    email_svc.send_email.assert_not_awaited()


@pytest.mark.asyncio
async def test_duplicate_membership_raises():
    acc = uuid4()
    existing = Identity(email="dup@x.com", password_hash="h", name="Dup")
    ident_repo = MagicMock(get_by_email=AsyncMock(return_value=existing))
    memb_repo = MagicMock(get_by_identity_and_account=AsyncMock(return_value=MagicMock()))
    uc = AddMemberUseCase(
        identity_repo=ident_repo, membership_repo=memb_repo, email_service=MagicMock()
    )
    with pytest.raises(ValueError):
        await uc.execute(
            account_id=acc, name="x", email="dup@x.com", role=UserRole.OPERATOR, profile_id=None
        )
