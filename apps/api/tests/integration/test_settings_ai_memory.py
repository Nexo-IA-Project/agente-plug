"""Integration-style tests for /admin/settings ai_memory_messages handling.

Estes testes usam TestClient + mocks dos use cases (mesmo padrão dos demais
testes de settings router) — não requerem postgres/redis reais.
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
        user_name="",
        must_change_password=False,
    )


def _make_config(ai_memory_messages: int = 20) -> AccountConfig:
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
        ),
        behavior=BehaviorConfig(
            idle_ping_minutes=30,
            idle_close_minutes=20,
            intent_confidence_threshold=0.7,
            message_buffer_wait_seconds=0,
            refund_deadline_days=7,
            welcome_d1_delay_hours=24,
            ai_memory_messages=ai_memory_messages,
        ),
    )


def _patched_scope(monkey_target: str):
    return patch(monkey_target)


def test_get_settings_includes_ai_memory_messages_default():
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
        uc_instance.execute = AsyncMock(return_value=_make_config(ai_memory_messages=20))
        MockUC.return_value = uc_instance

        r = client.get("/admin/settings")

    assert r.status_code == 200
    body = r.json()
    assert body["ai_memory_messages"] == 20


def test_put_settings_updates_ai_memory_messages():
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
        uc_instance.execute = AsyncMock(return_value=_make_config(ai_memory_messages=30))
        MockUC.return_value = uc_instance

        r = client.put("/admin/settings", json={"ai_memory_messages": 30})

    assert r.status_code == 200
    assert r.json()["ai_memory_messages"] == 30
    call_args = uc_instance.execute.call_args
    assert call_args.kwargs["patch"].ai_memory_messages == 30


def test_put_settings_rejects_out_of_range_ai_memory():
    app = _make_app()
    app.dependency_overrides[require_admin] = _auth_override
    client = TestClient(app)

    # Não esperamos que o use case seja chamado; pydantic deve barrar antes.
    r = client.put("/admin/settings", json={"ai_memory_messages": 200})
    assert r.status_code == 422

    r = client.put("/admin/settings", json={"ai_memory_messages": 3})
    assert r.status_code == 422
