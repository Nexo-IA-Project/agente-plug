from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Ensure the module is imported so patch paths resolve correctly.
import interface.http.routers.admin.users  # noqa: F401
from interface.http.deps.admin_auth import AdminAuth, require_admin_role


def _admin_auth():
    return AdminAuth(account_id=1, user_email="a@x.com", user_role="admin",
                     user_id="self-id", must_change_password=False)


def _make_app(auth_override):
    from interface.http.routers.admin.users import router
    app = FastAPI()
    app.include_router(router, prefix="/admin")
    app.dependency_overrides[require_admin_role] = lambda: auth_override
    return app


@pytest.mark.asyncio
async def test_create_user_201():
    from datetime import datetime
    fake_user = MagicMock()
    fake_user.id = "u1"
    fake_user.name = "X"
    fake_user.email = "x@x.com"
    fake_user.role = MagicMock(value="operator")
    fake_user.is_active = True
    fake_user.must_change_password = True
    fake_user.avatar = None
    fake_user.created_at = datetime(2026, 1, 1)
    fake_user.last_login_at = None

    with (
        patch("interface.http.routers.admin.users.session_scope") as mock_scope,
        patch("interface.http.routers.admin.users.CreateUserUseCase") as MockUC,
        patch("interface.http.routers.admin.users.SmtpEmailService"),
        patch("interface.http.routers.admin.users.SmtpConfigRepository"),
        patch("interface.http.routers.admin.users.UserRepository"),
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


def test_delete_self_blocked():
    app = _make_app(_admin_auth())
    client = TestClient(app)

    with patch("interface.http.routers.admin.users.session_scope") as mock_scope:
        session = AsyncMock()
        mock_scope.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_scope.return_value.__aexit__ = AsyncMock(return_value=False)
        r = client.delete("/admin/users/self-id")
        assert r.status_code == 409
