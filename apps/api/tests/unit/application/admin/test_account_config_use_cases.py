# apps/api/tests/unit/application/admin/test_account_config_use_cases.py
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from shared.application.use_cases.admin.get_account_config import GetAccountConfig
from shared.application.use_cases.admin.update_account_config import UpdateAccountConfig
from shared.domain.entities.account_config import (
    AccountConfig,
    AccountConfigPatch,
    BehaviorConfig,
    IntegrationConfig,
)


def _make_config() -> AccountConfig:
    return AccountConfig(
        integration=IntegrationConfig(
            chatnexo_base_url="http://nexo",
            chatnexo_api_key="key",
            hubla_webhook_secret="secret",
            cademi_api_url="",
            cademi_api_key="",
            cademi_max_retries=3,
            cademi_retry_base_seconds=1.0,
            openai_api_key="sk-test",
            meta_api_key="meta",
            meta_waba_id="",
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


@pytest.mark.asyncio
async def test_get_account_config_returns_config():
    repo = AsyncMock()
    repo.get = AsyncMock(return_value=_make_config())

    uc = GetAccountConfig(repo=repo)
    config = await uc.execute(account_id=1)

    assert config.integration.chatnexo_base_url == "http://nexo"
    repo.get.assert_called_once_with(account_id=1)


@pytest.mark.asyncio
async def test_update_account_config_delegates_to_repo():
    config = _make_config()
    repo = AsyncMock()
    repo.update = AsyncMock(return_value=config)

    uc = UpdateAccountConfig(repo=repo)
    patch = AccountConfigPatch(idle_ping_minutes=45)
    result = await uc.execute(account_id=1, patch=patch)

    assert result is config
    repo.update.assert_called_once_with(account_id=1, patch=patch)


@pytest.mark.asyncio
async def test_update_rejects_invalid_confidence_threshold():
    repo = AsyncMock()
    uc = UpdateAccountConfig(repo=repo)

    with pytest.raises(ValueError, match="intent_confidence_threshold"):
        await uc.execute(account_id=1, patch=AccountConfigPatch(intent_confidence_threshold=1.5))

    repo.update.assert_not_called()


@pytest.mark.asyncio
async def test_update_rejects_negative_max_retries():
    repo = AsyncMock()
    uc = UpdateAccountConfig(repo=repo)

    with pytest.raises(ValueError, match="cademi_max_retries"):
        await uc.execute(account_id=1, patch=AccountConfigPatch(cademi_max_retries=-1))

    repo.update.assert_not_called()
