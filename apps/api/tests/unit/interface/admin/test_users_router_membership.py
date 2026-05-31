from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from interface.http.deps.admin_auth import AdminAuth
from interface.http.routers.admin.users import _perm_manage, _perm_view
from shared.domain.entities.membership import Membership
from shared.domain.entities.user import UserRole


def _app():
    from interface.http.routers.admin.users import router

    app = FastAPI()
    app.include_router(router, prefix="/admin")
    auth = AdminAuth(
        account_id=uuid4(),
        user_email="admin@x.com",
        user_role="admin",
        user_id="id-admin",
        identity_id="id-admin",
        membership_id="m-admin",
        user_name="Admin",
        must_change_password=False,
    )
    app.dependency_overrides[_perm_manage] = lambda: auth
    app.dependency_overrides[_perm_view] = lambda: auth
    return app, auth


def _scoped_session():
    sess = AsyncMock()
    sess.__aenter__ = AsyncMock(return_value=sess)
    sess.__aexit__ = AsyncMock(return_value=False)
    return sess


@pytest.mark.asyncio
async def test_cannot_edit_owner_membership():
    app, auth = _app()
    owner = Membership(
        identity_id="id-owner",
        account_id=auth.account_id,
        role=UserRole.ADMIN,
        is_owner=True,
    )
    sess = _scoped_session()
    mr = MagicMock(get_by_id=AsyncMock(return_value=owner))
    with (
        patch("interface.http.routers.admin.users.session_scope", return_value=sess),
        patch("interface.http.routers.admin.users.MembershipRepository", return_value=mr),
    ):
        r = TestClient(app).put(
            f"/admin/users/{owner.id}",
            json={"name": "x", "role": "operator", "is_active": True, "profile_id": None},
        )
        assert r.status_code == 403


@pytest.mark.asyncio
async def test_cannot_delete_owner_membership():
    app, auth = _app()
    owner = Membership(
        identity_id="id-owner",
        account_id=auth.account_id,
        role=UserRole.ADMIN,
        is_owner=True,
    )
    sess = _scoped_session()
    mr = MagicMock(get_by_id=AsyncMock(return_value=owner))
    with (
        patch("interface.http.routers.admin.users.session_scope", return_value=sess),
        patch("interface.http.routers.admin.users.MembershipRepository", return_value=mr),
    ):
        r = TestClient(app).delete(f"/admin/users/{owner.id}")
        assert r.status_code == 403


@pytest.mark.asyncio
async def test_cannot_reset_owner_password():
    app, auth = _app()
    owner = Membership(
        identity_id="id-owner",
        account_id=auth.account_id,
        role=UserRole.ADMIN,
        is_owner=True,
    )
    sess = _scoped_session()
    mr = MagicMock(get_by_id=AsyncMock(return_value=owner))
    with (
        patch("interface.http.routers.admin.users.session_scope", return_value=sess),
        patch("interface.http.routers.admin.users.MembershipRepository", return_value=mr),
    ):
        r = TestClient(app).post(f"/admin/users/{owner.id}/reset-password")
        assert r.status_code == 403
