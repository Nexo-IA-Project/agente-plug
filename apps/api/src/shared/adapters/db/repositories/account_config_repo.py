# apps/api/src/shared/adapters/db/repositories/account_config_repo.py
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.adapters.db.models import AccountModel
from shared.adapters.db.repositories.chatnexo_agent_repo import ChatNexoAgentRepository
from shared.config.settings import get_settings
from shared.config.single_tenant import get_default_account_uuid
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
    # None = "não editado, manter como está".
    # Valor terminando em "****" = display mascarado retornado no GET (ex: "sk-proj-****" ou "****"),
    # não deve ser persistido.
    return value is None or value.endswith("****")


def _clamp_ai_memory(value: object, default: int = 20) -> int:
    """Le e clampa o valor de ai_memory_messages no range 5-100."""
    if value is None:
        v = default
    else:
        try:
            v = int(value)  # type: ignore[call-overload]
        except (TypeError, ValueError):
            v = default
    return max(5, min(100, v))


@dataclass
class AccountConfigRepository:
    session: AsyncSession
    fernet: Fernet

    async def _load_model(self) -> AccountModel | None:
        result = await self.session.execute(select(AccountModel).limit(1))
        return result.scalar_one_or_none()

    async def get(self, *, account_id: UUID) -> AccountConfig:
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

        # Carregar agentes ativos do ChatNexo
        agent_repo = ChatNexoAgentRepository(session=self.session, fernet=self.fernet)
        account_uuid = await get_default_account_uuid(self.session)
        agents = await agent_repo.list_active(account_uuid)

        return AccountConfig(
            integration=IntegrationConfig(
                chatnexo_base_url=gs("chatnexo_base_url", s.chatnexo_base_url),
                chatnexo_api_key=gs("chatnexo_api_key", s.chatnexo_api_key),
                chatnexo_account_id=int(i.get("chatnexo_account_id", s.chatnexo_account_id)),
                chatnexo_inbox_id=int(i.get("chatnexo_inbox_id", s.chatnexo_inbox_id)),
                hubla_webhook_secret=gs("hubla_webhook_secret", s.hubla_webhook_secret),
                meta_api_key=gs("meta_api_key", s.meta_api_key),
                meta_waba_id=i.get("meta_waba_id") or s.meta_waba_id,
                meta_app_id=i.get("meta_app_id") or (s.meta_app_id or ""),
                alert_whatsapp_target=i.get("alert_whatsapp_target") or None,
                chatnexo_agents=agents,
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
                ai_memory_messages=_clamp_ai_memory(b.get("ai_memory_messages")),
            ),
        )

    async def update(self, *, account_id: UUID, patch: AccountConfigPatch) -> AccountConfig:
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
            "meta_api_key",
            "meta_waba_id",
            "meta_app_id",
            "alert_whatsapp_target",
        ):
            val: str | None = getattr(patch, key)
            if _should_skip(val):
                continue
            assert val is not None
            i[key] = _encrypt(self.fernet, val) if key in _SENSITIVE else val

        if patch.chatnexo_account_id is not None:
            i["chatnexo_account_id"] = patch.chatnexo_account_id
        if patch.chatnexo_inbox_id is not None:
            i["chatnexo_inbox_id"] = patch.chatnexo_inbox_id

        for key in (
            "idle_ping_minutes",
            "idle_close_minutes",
            "intent_confidence_threshold",
            "message_buffer_wait_seconds",
            "refund_deadline_days",
            "welcome_d1_delay_hours",
            "ai_memory_messages",
        ):
            val_any = getattr(patch, key)
            if val_any is not None:
                b[key] = val_any

        current["integration"] = i
        current["behavior"] = b
        model.settings = current
        await self.session.flush()

        account_uuid = await get_default_account_uuid(self.session)
        return await self.get(account_id=account_uuid)
