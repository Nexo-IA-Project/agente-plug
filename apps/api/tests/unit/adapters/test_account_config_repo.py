# apps/api/tests/unit/adapters/test_account_config_repo.py
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from cryptography.fernet import Fernet

from shared.adapters.db.repositories.account_config_repo import (
    AccountConfigRepository,
    _mask,
)
from shared.domain.entities.account_config import AccountConfigPatch


def _make_fernet() -> Fernet:
    return Fernet(Fernet.generate_key())


def _make_repo(session: AsyncMock, fernet: Fernet) -> AccountConfigRepository:
    return AccountConfigRepository(session=session, fernet=fernet)


def _mock_account(settings_data: dict) -> MagicMock:
    m = MagicMock()
    m.settings = settings_data
    return m


def _mock_session_with_account(account_mock) -> AsyncMock:
    session = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = account_mock
    session.execute = AsyncMock(return_value=result_mock)
    return session


def _setup_default_settings(mock_s):
    s = mock_s.return_value
    s.chatnexo_base_url = "http://default"
    s.chatnexo_api_key = "default_key"
    s.hubla_webhook_secret = "default_secret"
    s.cademi_api_url = ""
    s.cademi_api_key = ""
    s.cademi_max_retries = 3
    s.cademi_retry_base_seconds = 1.0
    s.openai_api_key = "sk-default"
    s.meta_api_key = "meta_default"
    s.idle_ping_minutes = 30
    s.idle_close_minutes = 20
    s.intent_confidence_threshold = 0.7
    s.message_buffer_wait_seconds = 0
    s.refund_deadline_days = 7
    s.welcome_d1_delay_hours = 24
    s.loja_express_d1_delay_hours = 24
    s.loja_express_d3_delay_hours = 72
    s.loja_express_d5_delay_hours = 120
    s.loja_express_d7_delay_hours = 168


@pytest.mark.asyncio
async def test_get_returns_env_defaults_when_jsonb_empty():
    session = _mock_session_with_account(_mock_account({}))
    fernet = _make_fernet()
    repo = _make_repo(session, fernet)

    with patch("shared.adapters.db.repositories.account_config_repo.get_settings") as mock_s:
        _setup_default_settings(mock_s)
        config = await repo.get(account_id=1)

    assert config.integration.chatnexo_base_url == "http://default"
    assert config.integration.openai_api_key == "sk-default"
    assert config.behavior.idle_ping_minutes == 30
    assert config.behavior.refund_deadline_days == 7


@pytest.mark.asyncio
async def test_get_uses_db_values_over_env_defaults():
    fernet = _make_fernet()
    encrypted_key = fernet.encrypt(b"sk-db-key").decode()
    account = _mock_account(
        {
            "integration": {
                "chatnexo_base_url": "http://from-db",
                "openai_api_key": encrypted_key,
            },
            "behavior": {
                "idle_ping_minutes": 45,
            },
        }
    )
    session = _mock_session_with_account(account)
    repo = _make_repo(session, fernet)

    with patch("shared.adapters.db.repositories.account_config_repo.get_settings") as mock_s:
        _setup_default_settings(mock_s)
        config = await repo.get(account_id=1)

    assert config.integration.chatnexo_base_url == "http://from-db"
    assert config.integration.openai_api_key == "sk-db-key"
    assert config.behavior.idle_ping_minutes == 45
    assert config.behavior.refund_deadline_days == 7  # fallback env


@pytest.mark.asyncio
async def test_update_encrypts_sensitive_fields():
    fernet = _make_fernet()
    account = _mock_account({})
    session = _mock_session_with_account(account)
    repo = _make_repo(session, fernet)

    patch_obj = AccountConfigPatch(openai_api_key="sk-new-key")

    with patch("shared.adapters.db.repositories.account_config_repo.get_settings") as mock_s:
        _setup_default_settings(mock_s)
        await repo.update(account_id=1, patch=patch_obj)

    saved = account.settings
    stored_key = saved["integration"]["openai_api_key"]
    assert stored_key != "sk-new-key"
    assert fernet.decrypt(stored_key.encode()).decode() == "sk-new-key"


@pytest.mark.asyncio
async def test_update_ignores_masked_values():
    fernet = _make_fernet()
    encrypted_orig = fernet.encrypt(b"sk-original").decode()
    account = _mock_account({"integration": {"openai_api_key": encrypted_orig}})
    session = _mock_session_with_account(account)
    repo = _make_repo(session, fernet)

    patch_obj = AccountConfigPatch(openai_api_key="sk-proj-****abcd")

    with patch("shared.adapters.db.repositories.account_config_repo.get_settings") as mock_s:
        _setup_default_settings(mock_s)
        await repo.update(account_id=1, patch=patch_obj)

    saved = account.settings
    assert saved["integration"]["openai_api_key"] == encrypted_orig


def test_mask_hides_sensitive_values():
    assert _mask("sk-proj-abc123") == "sk-proj-****"
    assert _mask("short") == "****"
    assert _mask("") == ""
    assert _mask("12345678") == "12345678****"
