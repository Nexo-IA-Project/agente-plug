"""Testes para o campo alert_whatsapp_target em /admin/settings.

Espelha o padrão de test_settings_ai_memory.py — usa TestClient + mocks
dos use cases, sem postgres/redis reais.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

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
    return AdminAuth(
        account_id=1,
        user_email="admin@test.com",
        user_role="admin",
        user_id="test-id",
        identity_id="test-id",
        membership_id=None,
        user_name="",
        must_change_password=False,
    )


def _make_config(alert_whatsapp_target: str | None = None) -> AccountConfig:
    return AccountConfig(
        integration=IntegrationConfig(
            chatnexo_base_url="http://chatnexo",
            chatnexo_api_key="sk-chatnexo-key",
            chatnexo_account_id=1,
            chatnexo_inbox_id=1,
            hubla_webhook_secret="hubla-secret",
            meta_api_key="meta-key",
            meta_waba_id="123456789",
            meta_app_id="987654321",
            alert_whatsapp_target=alert_whatsapp_target,
        ),
        behavior=BehaviorConfig(
            idle_ping_minutes=30,
            idle_close_minutes=20,
            intent_confidence_threshold=0.7,
            message_buffer_wait_seconds=0,
            refund_deadline_days=7,
            welcome_d1_delay_hours=24,
        ),
    )


_FERNET_KEY = "miMM5SEWzPGSwr4F3RYIcp5voAgDStG65JDROm0JX1I="


def test_get_settings_returns_null_alert_whatsapp_target_by_default():
    app = _make_app()
    app.dependency_overrides[require_admin] = _auth_override
    client = TestClient(app)

    with (
        patch("interface.http.routers.admin.settings.session_scope") as mock_scope,
        patch("interface.http.routers.admin.settings.AccountConfigRepository"),
        patch("interface.http.routers.admin.settings.GetAccountConfig") as MockUC,
        patch("interface.http.routers.admin.settings.get_settings") as mock_settings,
    ):
        mock_settings.return_value.integration_credentials_key = _FERNET_KEY
        mock_session = AsyncMock()
        mock_scope.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_scope.return_value.__aexit__ = AsyncMock(return_value=False)

        uc_instance = AsyncMock()
        uc_instance.execute = AsyncMock(return_value=_make_config(alert_whatsapp_target=None))
        MockUC.return_value = uc_instance

        r = client.get("/admin/settings")

    assert r.status_code == 200
    body = r.json()
    assert body["alert_whatsapp_target"] is None


def test_get_settings_returns_alert_whatsapp_target_when_set():
    app = _make_app()
    app.dependency_overrides[require_admin] = _auth_override
    client = TestClient(app)

    with (
        patch("interface.http.routers.admin.settings.session_scope") as mock_scope,
        patch("interface.http.routers.admin.settings.AccountConfigRepository"),
        patch("interface.http.routers.admin.settings.GetAccountConfig") as MockUC,
        patch("interface.http.routers.admin.settings.get_settings") as mock_settings,
    ):
        mock_settings.return_value.integration_credentials_key = _FERNET_KEY
        mock_session = AsyncMock()
        mock_scope.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_scope.return_value.__aexit__ = AsyncMock(return_value=False)

        uc_instance = AsyncMock()
        uc_instance.execute = AsyncMock(
            return_value=_make_config(alert_whatsapp_target="+5511999990000")
        )
        MockUC.return_value = uc_instance

        r = client.get("/admin/settings")

    assert r.status_code == 200
    assert r.json()["alert_whatsapp_target"] == "+5511999990000"


def test_put_settings_persists_alert_whatsapp_target():
    """PUT com alert_whatsapp_target → patch recebe o valor e GET retorna."""
    app = _make_app()
    app.dependency_overrides[require_admin] = _auth_override
    client = TestClient(app)

    with (
        patch("interface.http.routers.admin.settings.session_scope") as mock_scope,
        patch("interface.http.routers.admin.settings.AccountConfigRepository"),
        patch("interface.http.routers.admin.settings.UpdateAccountConfig") as MockUC,
        patch("interface.http.routers.admin.settings.get_settings") as mock_settings,
    ):
        mock_settings.return_value.integration_credentials_key = _FERNET_KEY
        mock_session = AsyncMock()
        mock_scope.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_scope.return_value.__aexit__ = AsyncMock(return_value=False)

        uc_instance = AsyncMock()
        uc_instance.execute = AsyncMock(
            return_value=_make_config(alert_whatsapp_target="+5511999990000")
        )
        MockUC.return_value = uc_instance

        r = client.put("/admin/settings", json={"alert_whatsapp_target": "+5511999990000"})

    assert r.status_code == 200
    assert r.json()["alert_whatsapp_target"] == "+5511999990000"

    # verifica que o patch foi montado corretamente
    call_args = uc_instance.execute.call_args
    assert call_args.kwargs["patch"].alert_whatsapp_target == "+5511999990000"


def test_put_settings_clears_alert_whatsapp_target_with_none():
    """Enviar None no PUT não altera o campo (semântica de patch parcial)."""
    app = _make_app()
    app.dependency_overrides[require_admin] = _auth_override
    client = TestClient(app)

    with (
        patch("interface.http.routers.admin.settings.session_scope") as mock_scope,
        patch("interface.http.routers.admin.settings.AccountConfigRepository"),
        patch("interface.http.routers.admin.settings.UpdateAccountConfig") as MockUC,
        patch("interface.http.routers.admin.settings.get_settings") as mock_settings,
    ):
        mock_settings.return_value.integration_credentials_key = _FERNET_KEY
        mock_session = AsyncMock()
        mock_scope.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_scope.return_value.__aexit__ = AsyncMock(return_value=False)

        uc_instance = AsyncMock()
        # Simula que o valor existente é preservado quando patch é None
        uc_instance.execute = AsyncMock(
            return_value=_make_config(alert_whatsapp_target="+5511999990000")
        )
        MockUC.return_value = uc_instance

        # Sem alert_whatsapp_target no body → patch recebe None
        r = client.put("/admin/settings", json={"idle_ping_minutes": 45})

    assert r.status_code == 200
    call_args = uc_instance.execute.call_args
    assert call_args.kwargs["patch"].alert_whatsapp_target is None
