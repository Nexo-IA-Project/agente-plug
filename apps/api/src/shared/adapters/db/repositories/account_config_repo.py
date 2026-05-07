# apps/api/src/shared/adapters/db/repositories/account_config_repo.py
from __future__ import annotations

from dataclasses import dataclass

from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.adapters.db.models import AccountModel
from shared.config.settings import get_settings
from shared.domain.entities.account_config import (
    AccountConfig,
    AccountConfigPatch,
    BehaviorConfig,
    IntegrationConfig,
)

_SENSITIVE = frozenset(
    {
        "chatnexo_api_key",
        "hubla_webhook_secret",
        "cademi_api_key",
        "openai_api_key",
        "meta_api_key",
    }
)


def _mask(value: str) -> str:
    if not value:
        return ""
    if len(value) < 8:
        return "****"
    return value[:8] + "****"


def _decrypt(fernet: Fernet, value: str) -> str:
    try:
        return fernet.decrypt(value.encode()).decode()
    except Exception:
        return ""


def _encrypt(fernet: Fernet, value: str) -> str:
    return fernet.encrypt(value.encode()).decode()


def _should_skip(value: str | None) -> bool:
    return value is None or "****" in value


@dataclass
class AccountConfigRepository:
    session: AsyncSession
    fernet: Fernet

    async def _load_model(self) -> AccountModel | None:
        result = await self.session.execute(select(AccountModel).limit(1))
        return result.scalar_one_or_none()

    async def get(self, *, account_id: int) -> AccountConfig:  # noqa: ARG002
        model = await self._load_model()
        raw: dict = dict(model.settings or {}) if model else {}

        s = get_settings()
        i = raw.get("integration", {})
        b = raw.get("behavior", {})

        def gs(key: str, default: str) -> str:
            val = i.get(key) or ""
            if not val:
                return default
            if key in _SENSITIVE:
                return _decrypt(self.fernet, val)
            return val

        def gi(key: str, default: int) -> int:
            v = b.get(key)
            return int(v) if v is not None else default

        def gf(key: str, default: float) -> float:
            v = b.get(key)
            return float(v) if v is not None else default

        return AccountConfig(
            integration=IntegrationConfig(
                chatnexo_base_url=gs("chatnexo_base_url", s.chatnexo_base_url),
                chatnexo_api_key=gs("chatnexo_api_key", s.chatnexo_api_key),
                hubla_webhook_secret=gs("hubla_webhook_secret", s.hubla_webhook_secret),
                cademi_api_url=gs("cademi_api_url", s.cademi_api_url),
                cademi_api_key=gs("cademi_api_key", s.cademi_api_key),
                cademi_max_retries=int(i.get("cademi_max_retries", s.cademi_max_retries)),
                cademi_retry_base_seconds=float(
                    i.get("cademi_retry_base_seconds", s.cademi_retry_base_seconds)
                ),
                openai_api_key=gs("openai_api_key", s.openai_api_key),
                meta_api_key=gs("meta_api_key", s.meta_api_key),
            ),
            behavior=BehaviorConfig(
                idle_ping_minutes=gi("idle_ping_minutes", s.idle_ping_minutes),
                idle_close_minutes=gi("idle_close_minutes", s.idle_close_minutes),
                intent_confidence_threshold=gf(
                    "intent_confidence_threshold", s.intent_confidence_threshold
                ),
                message_buffer_wait_seconds=gi(
                    "message_buffer_wait_seconds", s.message_buffer_wait_seconds
                ),
                refund_deadline_days=gi("refund_deadline_days", s.refund_deadline_days),
                welcome_d1_delay_hours=gi("welcome_d1_delay_hours", s.welcome_d1_delay_hours),
                loja_express_d1_delay_hours=gi(
                    "loja_express_d1_delay_hours", s.loja_express_d1_delay_hours
                ),
                loja_express_d3_delay_hours=gi(
                    "loja_express_d3_delay_hours", s.loja_express_d3_delay_hours
                ),
                loja_express_d5_delay_hours=gi(
                    "loja_express_d5_delay_hours", s.loja_express_d5_delay_hours
                ),
                loja_express_d7_delay_hours=gi(
                    "loja_express_d7_delay_hours", s.loja_express_d7_delay_hours
                ),
            ),
        )

    async def update(self, *, account_id: int, patch: AccountConfigPatch) -> AccountConfig:  # noqa: ARG002
        model = await self._load_model()
        if model is None:
            model = AccountModel(name="default", settings={})
            self.session.add(model)
            await self.session.flush()

        current = dict(model.settings or {})
        i = dict(current.get("integration", {}))
        b = dict(current.get("behavior", {}))

        for key in (
            "chatnexo_base_url",
            "chatnexo_api_key",
            "hubla_webhook_secret",
            "cademi_api_url",
            "cademi_api_key",
            "openai_api_key",
            "meta_api_key",
        ):
            val: str | None = getattr(patch, key)
            if _should_skip(val):
                continue
            assert val is not None
            i[key] = _encrypt(self.fernet, val) if key in _SENSITIVE else val

        if patch.cademi_max_retries is not None:
            i["cademi_max_retries"] = patch.cademi_max_retries
        if patch.cademi_retry_base_seconds is not None:
            i["cademi_retry_base_seconds"] = patch.cademi_retry_base_seconds

        for key in (
            "idle_ping_minutes",
            "idle_close_minutes",
            "intent_confidence_threshold",
            "message_buffer_wait_seconds",
            "refund_deadline_days",
            "welcome_d1_delay_hours",
            "loja_express_d1_delay_hours",
            "loja_express_d3_delay_hours",
            "loja_express_d5_delay_hours",
            "loja_express_d7_delay_hours",
        ):
            val_any = getattr(patch, key)
            if val_any is not None:
                b[key] = val_any

        current["integration"] = i
        current["behavior"] = b
        model.settings = current
        await self.session.flush()

        return await self.get(account_id=1)
