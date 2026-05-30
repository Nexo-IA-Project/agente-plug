from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Ensure the module is imported so patch paths resolve correctly.
import interface.http.routers.admin.users
from interface.http.deps.admin_auth import AdminAuth, require_admin


def _admin_auth():
    return AdminAuth(
        account_id=1,
        user_email="a@x.com",
        user_role="admin",
        user_id="self-id",
        must_change_password=False,
    )


def _make_app(auth_override):
    from interface.http.routers.admin.users import router

    app = FastAPI()
    app.include_router(router, prefix="/admin")
    app.dependency_overrides[require_admin] = lambda: auth_override
    return app


def _fake_user(profile_id=None):
    from datetime import datetime

    u = MagicMock()
    u.id = "u1"
    u.name = "X"
    u.email = "x@x.com"
    u.role = MagicMock(value="operator")
    u.is_active = True
    u.must_change_password = True
    u.avatar = None
    u.created_at = datetime(2026, 1, 1)
    u.last_login_at = None
    u.profile_id = profile_id
    return u


@pytest.mark.asyncio
async def test_create_user_201():
    fake_user = _fake_user()

    with (
        patch("interface.http.routers.admin.users.session_scope") as mock_scope,
        patch("interface.http.routers.admin.users.CreateUserUseCase") as MockUC,
        patch("interface.http.routers.admin.users.SmtpEmailService"),
        patch("interface.http.routers.admin.users.PlatformConfigRepository"),
        patch("interface.http.routers.admin.users.UserRepository"),
        patch("interface.http.routers.admin.users.ProfileRepository"),
    ):
        session = AsyncMock()
        mock_scope.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_scope.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_uc_instance = MagicMock()
        mock_uc_instance.execute = AsyncMock(return_value=fake_user)
        MockUC.return_value = mock_uc_instance

        app = _make_app(_admin_auth())
        client = TestClient(app)
        r = client.post("/admin/users", json={"name": "X", "email": "x@x.com", "role": "operator"})
        assert r.status_code == 201


@pytest.mark.asyncio
async def test_create_user_with_valid_profile():
    pid = uuid.uuid4()
    fake_user = _fake_user(profile_id=pid)
    profile = MagicMock()
    profile.id = pid
    profile.name = "Suporte"

    with (
        patch("interface.http.routers.admin.users.session_scope") as mock_scope,
        patch("interface.http.routers.admin.users.CreateUserUseCase") as MockUC,
        patch("interface.http.routers.admin.users.SmtpEmailService"),
        patch("interface.http.routers.admin.users.PlatformConfigRepository"),
        patch("interface.http.routers.admin.users.UserRepository"),
        patch("interface.http.routers.admin.users.ProfileRepository") as MockProfileRepo,
    ):
        session = AsyncMock()
        mock_scope.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_scope.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_uc_instance = MagicMock()
        mock_uc_instance.execute = AsyncMock(return_value=fake_user)
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
        patch("interface.http.routers.admin.users.CreateUserUseCase"),
        patch("interface.http.routers.admin.users.SmtpEmailService"),
        patch("interface.http.routers.admin.users.PlatformConfigRepository"),
        patch("interface.http.routers.admin.users.UserRepository"),
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
async def test_update_user_changes_profile():
    pid = uuid.uuid4()
    existing = _fake_user()
    existing.role = interface.http.routers.admin.users.UserRole.OPERATOR
    existing.account_id = 1
    updated = _fake_user(profile_id=pid)
    profile = MagicMock()
    profile.id = pid
    profile.name = "Suporte"

    with (
        patch("interface.http.routers.admin.users.session_scope") as mock_scope,
        patch("interface.http.routers.admin.users.UserRepository") as MockUserRepo,
        patch("interface.http.routers.admin.users.ProfileRepository") as MockProfileRepo,
    ):
        session = AsyncMock()
        mock_scope.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_scope.return_value.__aexit__ = AsyncMock(return_value=False)
        user_repo = MagicMock()
        user_repo.get_by_id = AsyncMock(side_effect=[existing, updated])
        user_repo.update_admin_fields = AsyncMock()
        MockUserRepo.return_value = user_repo
        profile_repo = MagicMock()
        profile_repo.get_by_id = AsyncMock(return_value=profile)
        MockProfileRepo.return_value = profile_repo

        app = _make_app(_admin_auth())
        client = TestClient(app)
        r = client.put(
            "/admin/users/u1",
            json={
                "name": "X",
                "role": "operator",
                "is_active": True,
                "profile_id": str(pid),
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert body["profile_id"] == str(pid)
        assert body["profile_name"] == "Suporte"
        # profile_id propagated to repo
        _, kwargs = user_repo.update_admin_fields.call_args
        assert str(kwargs["profile_id"]) == str(pid)


@pytest.mark.asyncio
async def test_update_user_clears_profile():
    existing = _fake_user(profile_id=uuid.uuid4())
    existing.role = interface.http.routers.admin.users.UserRole.OPERATOR
    existing.account_id = 1
    updated = _fake_user(profile_id=None)

    with (
        patch("interface.http.routers.admin.users.session_scope") as mock_scope,
        patch("interface.http.routers.admin.users.UserRepository") as MockUserRepo,
        patch("interface.http.routers.admin.users.ProfileRepository"),
    ):
        session = AsyncMock()
        mock_scope.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_scope.return_value.__aexit__ = AsyncMock(return_value=False)
        user_repo = MagicMock()
        user_repo.get_by_id = AsyncMock(side_effect=[existing, updated])
        user_repo.update_admin_fields = AsyncMock()
        MockUserRepo.return_value = user_repo

        app = _make_app(_admin_auth())
        client = TestClient(app)
        r = client.put(
            "/admin/users/u1",
            json={"name": "X", "role": "operator", "is_active": True, "profile_id": None},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["profile_id"] is None
        assert body["profile_name"] is None
        _, kwargs = user_repo.update_admin_fields.call_args
        assert kwargs["profile_id"] is None


@pytest.mark.asyncio
async def test_list_users_includes_profile_name():
    pid = uuid.uuid4()
    u = _fake_user(profile_id=pid)

    with (
        patch("interface.http.routers.admin.users.session_scope") as mock_scope,
        patch("interface.http.routers.admin.users.UserRepository") as MockUserRepo,
        patch("interface.http.routers.admin.users.ProfileRepository") as MockProfileRepo,
    ):
        session = AsyncMock()
        mock_scope.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_scope.return_value.__aexit__ = AsyncMock(return_value=False)
        user_repo = MagicMock()
        user_repo.list_by_account = AsyncMock(return_value=([u], 1))
        MockUserRepo.return_value = user_repo
        profile_repo = MagicMock()
        profile_repo.name_map = AsyncMock(return_value={pid: "Suporte"})
        MockProfileRepo.return_value = profile_repo

        app = _make_app(_admin_auth())
        client = TestClient(app)
        r = client.get("/admin/users")
        assert r.status_code == 200
        body = r.json()
        assert body["items"][0]["profile_id"] == str(pid)
        assert body["items"][0]["profile_name"] == "Suporte"


def test_delete_self_blocked():
    app = _make_app(_admin_auth())
    client = TestClient(app)

    with patch("interface.http.routers.admin.users.session_scope") as mock_scope:
        session = AsyncMock()
        mock_scope.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_scope.return_value.__aexit__ = AsyncMock(return_value=False)
        r = client.delete("/admin/users/self-id")
        assert r.status_code == 409
