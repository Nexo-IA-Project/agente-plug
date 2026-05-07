# apps/api/tests/unit/interface/admin/test_settings_router.py
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from interface.http.deps.admin_auth import AdminAuth, require_admin
from interface.http.routers.admin import settings as settings_router
from shared.domain.entities.account_config import (
    AccountConfig,
    BehaviorConfig,
    IntegrationConfig,
)


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(settings_router.router, prefix="/admin")
    return app


def _auth_override() -> AdminAuth:
    return AdminAuth(account_id=1, user_email="admin@test.com", user_role="admin")


def _make_config() -> AccountConfig:
    return AccountConfig(
        integration=IntegrationConfig(
            chatnexo_base_url="http://chatnexo",
            chatnexo_api_key="sk-chatnexo-key",
            hubla_webhook_secret="hubla-secret",
            cademi_api_url="http://cademi",
            cademi_api_key="cademi-key",
            cademi_max_retries=3,
            cademi_retry_base_seconds=1.0,
            openai_api_key="sk-proj-openai-key",
            meta_api_key="meta-key",
        ),
        behavior=BehaviorConfig(
            idle_ping_minutes=30,
            idle_close_minutes=20,
            intent_confidence_threshold=0.7,
            message_buffer_wait_seconds=0,
            refund_deadline_days=7,
            welcome_d1_delay_hours=24,
            loja_express_d1_delay_hours=24,
            loja_express_d3_delay_hours=72,
            loja_express_d5_delay_hours=120,
            loja_express_d7_delay_hours=168,
        ),
    )


def test_get_settings_returns_masked_api_keys():
    app = _make_app()
    app.dependency_overrides[require_admin] = _auth_override
    client = TestClient(app)

    with (
        patch("interface.http.routers.admin.settings.session_scope") as mock_scope,
        patch("interface.http.routers.admin.settings.AccountConfigRepository"),
        patch("interface.http.routers.admin.settings.GetAccountConfig") as MockUC,
        patch("interface.http.routers.admin.settings.get_settings") as mock_settings,
    ):
        mock_settings.return_value.integration_credentials_key = (
            "miMM5SEWzPGSwr4F3RYIcp5voAgDStG65JDROm0JX1I="
        )
        mock_session = AsyncMock()
        mock_scope.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_scope.return_value.__aexit__ = AsyncMock(return_value=False)

        uc_instance = AsyncMock()
        uc_instance.execute = AsyncMock(return_value=_make_config())
        MockUC.return_value = uc_instance

        r = client.get("/admin/settings")

    assert r.status_code == 200
    data = r.json()
    assert "****" in data["chatnexo_api_key"]
    assert "****" in data["openai_api_key"]
    assert data["chatnexo_base_url"] == "http://chatnexo"
    assert data["idle_ping_minutes"] == 30


def test_put_settings_accepts_partial_patch():
    app = _make_app()
    app.dependency_overrides[require_admin] = _auth_override
    client = TestClient(app)

    with (
        patch("interface.http.routers.admin.settings.session_scope") as mock_scope,
        patch("interface.http.routers.admin.settings.AccountConfigRepository"),
        patch("interface.http.routers.admin.settings.UpdateAccountConfig") as MockUC,
        patch("interface.http.routers.admin.settings.get_settings") as mock_settings,
    ):
        mock_settings.return_value.integration_credentials_key = (
            "miMM5SEWzPGSwr4F3RYIcp5voAgDStG65JDROm0JX1I="
        )
        mock_session = AsyncMock()
        mock_scope.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_scope.return_value.__aexit__ = AsyncMock(return_value=False)

        uc_instance = AsyncMock()
        uc_instance.execute = AsyncMock(return_value=_make_config())
        MockUC.return_value = uc_instance

        r = client.put("/admin/settings", json={"idle_ping_minutes": 45})

    assert r.status_code == 200
    call_args = uc_instance.execute.call_args
    assert call_args.kwargs["patch"].idle_ping_minutes == 45


def test_put_settings_returns_422_for_invalid_value():
    app = _make_app()
    app.dependency_overrides[require_admin] = _auth_override
    client = TestClient(app)

    with (
        patch("interface.http.routers.admin.settings.session_scope") as mock_scope,
        patch("interface.http.routers.admin.settings.AccountConfigRepository"),
        patch("interface.http.routers.admin.settings.UpdateAccountConfig") as MockUC,
        patch("interface.http.routers.admin.settings.get_settings") as mock_settings,
    ):
        mock_settings.return_value.integration_credentials_key = (
            "miMM5SEWzPGSwr4F3RYIcp5voAgDStG65JDROm0JX1I="
        )
        mock_session = AsyncMock()
        mock_scope.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_scope.return_value.__aexit__ = AsyncMock(return_value=False)

        uc_instance = AsyncMock()
        uc_instance.execute.side_effect = ValueError(
            "intent_confidence_threshold deve estar entre 0.0 e 1.0"
        )
        MockUC.return_value = uc_instance

        r = client.put("/admin/settings", json={"intent_confidence_threshold": 2.0})

    assert r.status_code == 422


def test_get_settings_returns_401_without_auth():
    app = _make_app()
    client = TestClient(app, raise_server_exceptions=False)
    r = client.get("/admin/settings")
    assert r.status_code == 401
