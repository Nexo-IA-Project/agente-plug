# apps/api/src/shared/domain/entities/account_config.py
from __future__ import annotations

from dataclasses import dataclass, field

from shared.domain.entities.chatnexo_agent import ChatNexoAgent


@dataclass(frozen=True)
class IntegrationConfig:
    chatnexo_base_url: str
    chatnexo_api_key: str
    chatnexo_account_id: int
    chatnexo_inbox_id: int
    hubla_webhook_secret: str
    meta_api_key: str
    meta_waba_id: str
    meta_app_id: str
    alert_whatsapp_target: str | None = field(default=None)
    chatnexo_agents: list[ChatNexoAgent] = field(default_factory=list)


@dataclass(frozen=True)
class BehaviorConfig:
    idle_ping_minutes: int
    idle_close_minutes: int
    intent_confidence_threshold: float
    message_buffer_wait_seconds: int
    refund_deadline_days: int
    welcome_d1_delay_hours: int
    ai_memory_messages: int = 20


@dataclass(frozen=True)
class AccountConfig:
    integration: IntegrationConfig
    behavior: BehaviorConfig


@dataclass
class AccountConfigPatch:
    """Patch parcial — apenas campos não-None são atualizados."""

    chatnexo_base_url: str | None = field(default=None)
    chatnexo_api_key: str | None = field(default=None)
    chatnexo_account_id: int | None = field(default=None)
    chatnexo_inbox_id: int | None = field(default=None)
    hubla_webhook_secret: str | None = field(default=None)
    meta_api_key: str | None = field(default=None)
    meta_waba_id: str | None = field(default=None)
    meta_app_id: str | None = field(default=None)
    alert_whatsapp_target: str | None = field(default=None)
    idle_ping_minutes: int | None = field(default=None)
    idle_close_minutes: int | None = field(default=None)
    intent_confidence_threshold: float | None = field(default=None)
    message_buffer_wait_seconds: int | None = field(default=None)
    refund_deadline_days: int | None = field(default=None)
    welcome_d1_delay_hours: int | None = field(default=None)
    ai_memory_messages: int | None = field(default=None)
