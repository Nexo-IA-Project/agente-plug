from __future__ import annotations

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from interface.http.deps.admin_auth import AdminAuth
from interface.http.routers.admin.users import _perm_manage, _perm_view
from shared.domain.entities.membership import Membership
from shared.domain.entities.user import UserRole

ACCOUNT_ID = uuid.uuid4()


def _admin_auth():
    return AdminAuth(
        account_id=ACCOUNT_ID,
        user_email="a@x.com",
        user_role="admin",
        user_id="self-id",
        identity_id="self-id",
        membership_id="m-self",
        user_name="",
        must_change_password=False,
    )


def _make_app(auth_override):
    from interface.http.routers.admin.users import router

    app = FastAPI()
    app.include_router(router, prefix="/admin")
    app.dependency_overrides[_perm_manage] = lambda: auth_override
    app.dependency_overrides[_perm_view] = lambda: auth_override
    return app


def _member_view(profile_id=None, membership_id="m1", identity_id="id1"):
    from shared.adapters.db.repositories.membership_repo import MemberView

    return MemberView(
        membership_id=membership_id,
        identity_id=identity_id,
        account_id=ACCOUNT_ID,
        account_name="Acme",
        email="x@x.com",
        name="X",
        role=UserRole.OPERATOR,
        profile_id=profile_id,
        is_owner=False,
        is_active=True,
        must_change_password=True,
        has_avatar=False,
        created_at=datetime(2026, 1, 1),
        last_login_at=None,
    )


def _add_member_result(membership_id="m1", profile_id=None):
    membership = Membership(
        id=membership_id,
        identity_id="id1",
        account_id=ACCOUNT_ID,
        role=UserRole.OPERATOR,
        profile_id=profile_id,
        is_owner=False,
        is_active=True,
    )
    identity = MagicMock()
    identity.id = "id1"
    identity.name = "X"
    identity.email = "x@x.com"
    identity.must_change_password = True
    identity.avatar = None
    identity.last_login_at = None
    result = MagicMock()
    result.membership = membership
    result.identity = identity
    result.created_identity = True
    return result


@pytest.mark.asyncio
async def test_create_user_201():
    with (
        patch("interface.http.routers.admin.users.session_scope") as mock_scope,
        patch("interface.http.routers.admin.users.AddMemberUseCase") as MockUC,
        patch("interface.http.routers.admin.users.SmtpEmailService"),
        patch("interface.http.routers.admin.users.PlatformConfigRepository"),
        patch("interface.http.routers.admin.users.IdentityRepository"),
        patch("interface.http.routers.admin.users.MembershipRepository"),
        patch("interface.http.routers.admin.users.ProfileRepository"),
    ):
        session = AsyncMock()
        mock_scope.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_scope.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_uc_instance = MagicMock()
        mock_uc_instance.execute = AsyncMock(return_value=_add_member_result())
        MockUC.return_value = mock_uc_instance

        app = _make_app(_admin_auth())
        client = TestClient(app)
        r = client.post("/admin/users", json={"name": "X", "email": "x@x.com", "role": "operator"})
        assert r.status_code == 201
        assert r.json()["id"] == "m1"


@pytest.mark.asyncio
async def test_create_user_with_valid_profile():
    pid = uuid.uuid4()
    profile = MagicMock()
    profile.id = pid
    profile.name = "Suporte"

    with (
        patch("interface.http.routers.admin.users.session_scope") as mock_scope,
        patch("interface.http.routers.admin.users.AddMemberUseCase") as MockUC,
        patch("interface.http.routers.admin.users.SmtpEmailService"),
        patch("interface.http.routers.admin.users.PlatformConfigRepository"),
        patch("interface.http.routers.admin.users.IdentityRepository"),
        patch("interface.http.routers.admin.users.MembershipRepository"),
        patch("interface.http.routers.admin.users.ProfileRepository") as MockProfileRepo,
    ):
        session = AsyncMock()
        mock_scope.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_scope.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_uc_instance = MagicMock()
        mock_uc_instance.execute = AsyncMock(return_value=_add_member_result(profile_id=pid))
        MockUC.return_value = mock_uc_instance
        profile_repo = MagicMock()
        profile_repo.get_by_id = AsyncMock(return_value=profile)
        MockProfileRepo.return_value = profile_repo

        app = _make_app(_admin_auth())
        client = TestClient(app)
        r = client.post(
            "/admin/users",
            json={"name": "X", "email": "x@x.com", "role": "operator", "profile_id": str(pid)},
        )
        assert r.status_code == 201
        body = r.json()
        assert body["profile_id"] == str(pid)
        assert body["profile_name"] == "Suporte"


@pytest.mark.asyncio
async def test_create_user_with_invalid_profile():
    pid = uuid.uuid4()

    with (
        patch("interface.http.routers.admin.users.session_scope") as mock_scope,
        patch("interface.http.routers.admin.users.AddMemberUseCase"),
        patch("interface.http.routers.admin.users.SmtpEmailService"),
        patch("interface.http.routers.admin.users.PlatformConfigRepository"),
        patch("interface.http.routers.admin.users.IdentityRepository"),
        patch("interface.http.routers.admin.users.MembershipRepository"),
        patch("interface.http.routers.admin.users.ProfileRepository") as MockProfileRepo,
    ):
        session = AsyncMock()
        mock_scope.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_scope.return_value.__aexit__ = AsyncMock(return_value=False)
        profile_repo = MagicMock()
        profile_repo.get_by_id = AsyncMock(return_value=None)
        MockProfileRepo.return_value = profile_repo

        app = _make_app(_admin_auth())
        client = TestClient(app)
        r = client.post(
            "/admin/users",
            json={"name": "X", "email": "x@x.com", "role": "operator", "profile_id": str(pid)},
        )
        assert r.status_code == 400


@pytest.mark.asyncio
async def test_create_user_duplicate_member_409():
    with (
        patch("interface.http.routers.admin.users.session_scope") as mock_scope,
        patch("interface.http.routers.admin.users.AddMemberUseCase") as MockUC,
        patch("interface.http.routers.admin.users.SmtpEmailService"),
        patch("interface.http.routers.admin.users.PlatformConfigRepository"),
        patch("interface.http.routers.admin.users.IdentityRepository"),
        patch("interface.http.routers.admin.users.MembershipRepository"),
        patch("interface.http.routers.admin.users.ProfileRepository"),
    ):
        session = AsyncMock()
        mock_scope.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_scope.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_uc_instance = MagicMock()
        mock_uc_instance.execute = AsyncMock(side_effect=ValueError("já faz parte"))
        MockUC.return_value = mock_uc_instance

        app = _make_app(_admin_auth())
        client = TestClient(app)
        r = client.post("/admin/users", json={"name": "X", "email": "x@x.com", "role": "operator"})
        assert r.status_code == 409


@pytest.mark.asyncio
async def test_update_user_changes_profile():
    pid = uuid.uuid4()
    existing = Membership(
        id="m1",
        identity_id="id1",
        account_id=ACCOUNT_ID,
        role=UserRole.OPERATOR,
        is_owner=False,
        is_active=True,
    )
    profile = MagicMock()
    profile.id = pid
    profile.name = "Suporte"

    with (
        patch("interface.http.routers.admin.users.session_scope") as mock_scope,
        patch("interface.http.routers.admin.users.MembershipRepository") as MockMembershipRepo,
        patch("interface.http.routers.admin.users.IdentityRepository") as MockIdentityRepo,
        patch("interface.http.routers.admin.users.ProfileRepository") as MockProfileRepo,
    ):
        session = AsyncMock()
        mock_scope.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_scope.return_value.__aexit__ = AsyncMock(return_value=False)
        membership_repo = MagicMock()
        membership_repo.get_by_id = AsyncMock(return_value=existing)
        membership_repo.update_fields = AsyncMock()
        membership_repo.count_active_admins = AsyncMock(return_value=2)
        MockMembershipRepo.return_value = membership_repo
        identity = MagicMock()
        identity.email = "x@x.com"
        identity.must_change_password = True
        identity.avatar = None
        identity.last_login_at = None
        identity_repo = MagicMock()
        identity_repo.update_profile = AsyncMock()
        identity_repo.get_by_id = AsyncMock(return_value=identity)
        MockIdentityRepo.return_value = identity_repo
        profile_repo = MagicMock()
        profile_repo.get_by_id = AsyncMock(return_value=profile)
        MockProfileRepo.return_value = profile_repo

        app = _make_app(_admin_auth())
        client = TestClient(app)
        r = client.put(
            "/admin/users/m1",
            json={
                "name": "X",
                "role": "operator",
                "is_active": True,
                "profile_id": str(pid),
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert body["id"] == "m1"
        assert body["profile_id"] == str(pid)
        assert body["profile_name"] == "Suporte"
        _, kwargs = membership_repo.update_fields.call_args
        assert str(kwargs["profile_id"]) == str(pid)
        identity_repo.update_profile.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_user_clears_profile():
    existing = Membership(
        id="m1",
        identity_id="id1",
        account_id=ACCOUNT_ID,
        role=UserRole.OPERATOR,
        profile_id=uuid.uuid4(),
        is_owner=False,
        is_active=True,
    )

    with (
        patch("interface.http.routers.admin.users.session_scope") as mock_scope,
        patch("interface.http.routers.admin.users.MembershipRepository") as MockMembershipRepo,
        patch("interface.http.routers.admin.users.IdentityRepository") as MockIdentityRepo,
        patch("interface.http.routers.admin.users.ProfileRepository"),
    ):
        session = AsyncMock()
        mock_scope.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_scope.return_value.__aexit__ = AsyncMock(return_value=False)
        membership_repo = MagicMock()
        membership_repo.get_by_id = AsyncMock(return_value=existing)
        membership_repo.update_fields = AsyncMock()
        membership_repo.count_active_admins = AsyncMock(return_value=2)
        MockMembershipRepo.return_value = membership_repo
        identity = MagicMock()
        identity.email = "x@x.com"
        identity.must_change_password = True
        identity.avatar = None
        identity.last_login_at = None
        identity_repo = MagicMock()
        identity_repo.update_profile = AsyncMock()
        identity_repo.get_by_id = AsyncMock(return_value=identity)
        MockIdentityRepo.return_value = identity_repo

        app = _make_app(_admin_auth())
        client = TestClient(app)
        r = client.put(
            "/admin/users/m1",
            json={"name": "X", "role": "operator", "is_active": True, "profile_id": None},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["profile_id"] is None
        assert body["profile_name"] is None
        _, kwargs = membership_repo.update_fields.call_args
        assert kwargs["profile_id"] is None


@pytest.mark.asyncio
async def test_update_user_not_found_other_account():
    other = Membership(
        id="m1",
        identity_id="id1",
        account_id=uuid.uuid4(),  # conta diferente
        role=UserRole.OPERATOR,
        is_owner=False,
        is_active=True,
    )
    with (
        patch("interface.http.routers.admin.users.session_scope") as mock_scope,
        patch("interface.http.routers.admin.users.MembershipRepository") as MockMembershipRepo,
        patch("interface.http.routers.admin.users.IdentityRepository"),
        patch("interface.http.routers.admin.users.ProfileRepository"),
    ):
        session = AsyncMock()
        mock_scope.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_scope.return_value.__aexit__ = AsyncMock(return_value=False)
        membership_repo = MagicMock()
        membership_repo.get_by_id = AsyncMock(return_value=other)
        MockMembershipRepo.return_value = membership_repo

        app = _make_app(_admin_auth())
        client = TestClient(app)
        r = client.put(
            "/admin/users/m1",
            json={"name": "X", "role": "operator", "is_active": True, "profile_id": None},
        )
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_list_users_includes_profile_name():
    pid = uuid.uuid4()
    v = _member_view(profile_id=pid)

    with (
        patch("interface.http.routers.admin.users.session_scope") as mock_scope,
        patch("interface.http.routers.admin.users.MembershipRepository") as MockMembershipRepo,
        patch("interface.http.routers.admin.users.ProfileRepository") as MockProfileRepo,
    ):
        session = AsyncMock()
        mock_scope.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_scope.return_value.__aexit__ = AsyncMock(return_value=False)
        membership_repo = MagicMock()
        membership_repo.list_by_account = AsyncMock(return_value=([v], 1))
        MockMembershipRepo.return_value = membership_repo
        profile_repo = MagicMock()
        profile_repo.name_map = AsyncMock(return_value={pid: "Suporte"})
        MockProfileRepo.return_value = profile_repo

        app = _make_app(_admin_auth())
        client = TestClient(app)
        r = client.get("/admin/users")
        assert r.status_code == 200
        body = r.json()
        assert body["items"][0]["id"] == "m1"
        assert body["items"][0]["profile_id"] == str(pid)
        assert body["items"][0]["profile_name"] == "Suporte"


def test_delete_self_blocked():
    # Membership cujo identity_id == auth.identity_id ("self-id")
    existing = Membership(
        id="m-self",
        identity_id="self-id",
        account_id=ACCOUNT_ID,
        role=UserRole.OPERATOR,
        is_owner=False,
        is_active=True,
    )
    app = _make_app(_admin_auth())
    client = TestClient(app)

    with (
        patch("interface.http.routers.admin.users.session_scope") as mock_scope,
        patch("interface.http.routers.admin.users.MembershipRepository") as MockMembershipRepo,
    ):
        session = AsyncMock()
        mock_scope.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_scope.return_value.__aexit__ = AsyncMock(return_value=False)
        membership_repo = MagicMock()
        membership_repo.get_by_id = AsyncMock(return_value=existing)
        MockMembershipRepo.return_value = membership_repo
        r = client.delete("/admin/users/m-self")
        assert r.status_code == 409
