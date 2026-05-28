from __future__ import annotations

import base64
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from interface.http.deps.admin_auth import AdminAuth, require_admin


def _auth(role="admin"):
    return AdminAuth(account_id=1, user_email="x@x.com", user_role=role,
                     user_id="uid", must_change_password=False)


def _make_app(auth):
    from interface.http.routers.admin.me import router
    app = FastAPI()
    app.include_router(router, prefix="/admin")
    app.dependency_overrides[require_admin] = lambda: auth
    return app


def test_get_me_returns_user():
    fake_user = MagicMock()
    fake_user.id = "uid"
    fake_user.name = "Fabio"
    fake_user.email = "f@x.com"
    fake_user.role = MagicMock(value="admin")
    fake_user.must_change_password = False
    fake_user.avatar = None
    with patch("interface.http.routers.admin.me.session_scope") as mock_scope:
        s = AsyncMock()
        mock_scope.return_value.__aenter__ = AsyncMock(return_value=s)
        mock_scope.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("interface.http.routers.admin.me.UserRepository") as MockRepo:
            instance = MagicMock()
            instance.get_by_id = AsyncMock(return_value=fake_user)
            MockRepo.return_value = instance

            app = _make_app(_auth())
            client = TestClient(app)
            r = client.get("/admin/me")
            assert r.status_code == 200
            assert r.json()["name"] == "Fabio"


def test_update_avatar_rejects_oversized():
    big = b"x" * (250 * 1024)
    payload = base64.b64encode(big).decode()
    app = _make_app(_auth())
    client = TestClient(app)
    r = client.put("/admin/me/avatar", json={"data": payload})
    assert r.status_code == 413


def test_update_avatar_rejects_invalid_base64():
    app = _make_app(_auth())
    client = TestClient(app)
    r = client.put("/admin/me/avatar", json={"data": "not!!!base64!!!"})
    assert r.status_code == 422
