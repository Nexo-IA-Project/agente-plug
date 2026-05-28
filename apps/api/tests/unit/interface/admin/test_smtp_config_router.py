from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from interface.http.deps.admin_auth import AdminAuth, require_admin_role


def _auth():
    return AdminAuth(account_id=1, user_email="x@x.com", user_role="admin",
                     user_id="uid", must_change_password=False)


def _make_app(auth):
    from interface.http.routers.admin.smtp_config import router
    app = FastAPI()
    app.include_router(router, prefix="/admin")
    app.dependency_overrides[require_admin_role] = lambda: auth
    return app


def _mock_scope(mock_scope, repo_instance):
    s = AsyncMock()
    mock_scope.return_value.__aenter__ = AsyncMock(return_value=s)
    mock_scope.return_value.__aexit__ = AsyncMock(return_value=False)


def test_get_returns_null_when_not_configured():
    with patch("interface.http.routers.admin.smtp_config.session_scope") as mock_scope:
        _mock_scope(mock_scope, None)
        with patch("interface.http.routers.admin.smtp_config.SmtpConfigRepository") as MockRepo:
            instance = MagicMock()
            instance.get = AsyncMock(return_value=None)
            MockRepo.return_value = instance

            app = _make_app(_auth())
            client = TestClient(app)
            r = client.get("/admin/smtp-config")
            assert r.status_code == 200
            assert r.json() is None


def test_put_creates_new_config():
    with patch("interface.http.routers.admin.smtp_config.session_scope") as mock_scope:
        _mock_scope(mock_scope, None)
        with patch("interface.http.routers.admin.smtp_config.SmtpConfigRepository") as MockRepo:
            instance = MagicMock()
            instance.get = AsyncMock(return_value=None)
            saved = MagicMock(host="smtp.test", port=587, username="u", use_tls=True,
                              from_name="N", from_email="from@x.com")
            instance.upsert = AsyncMock(return_value=saved)
            MockRepo.return_value = instance

            app = _make_app(_auth())
            client = TestClient(app)
            r = client.put("/admin/smtp-config", json={
                "host": "smtp.test", "port": 587, "username": "u",
                "password": "secret", "use_tls": True,
                "from_name": "N", "from_email": "from@x.com",
            })
            assert r.status_code == 200
            assert r.json()["host"] == "smtp.test"


def test_put_rejects_missing_password_on_first_config():
    with patch("interface.http.routers.admin.smtp_config.session_scope") as mock_scope:
        _mock_scope(mock_scope, None)
        with patch("interface.http.routers.admin.smtp_config.SmtpConfigRepository") as MockRepo:
            instance = MagicMock()
            instance.get = AsyncMock(return_value=None)
            MockRepo.return_value = instance

            app = _make_app(_auth())
            client = TestClient(app)
            r = client.put("/admin/smtp-config", json={
                "host": "h", "port": 587, "username": "u",
                "use_tls": True, "from_name": "N", "from_email": "f@x.com",
            })
            assert r.status_code == 422
