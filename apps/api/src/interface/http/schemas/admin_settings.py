# apps/api/src/interface/http/schemas/admin_settings.py
from __future__ import annotations

from pydantic import BaseModel, Field


class AccountSettingsResponse(BaseModel):
    # Integrações
    chatnexo_base_url: str
    chatnexo_api_key: str
    chatnexo_account_id: int
    chatnexo_inbox_id: int
    hubla_webhook_secret: str
    meta_api_key: str
    meta_waba_id: str
    meta_app_id: str
    alert_whatsapp_target: str | None = None
    # Comportamento
    idle_ping_minutes: int
    idle_close_minutes: int
    intent_confidence_threshold: float
    message_buffer_wait_seconds: int
    refund_deadline_days: int
    welcome_d1_delay_hours: int
    ai_memory_messages: int
    # Message Buffer
    message_buffer_enabled: bool = False
    message_buffer_outgoing_url: str | None = None
    message_buffer_api_key: str | None = None
    message_buffer_tenant_id: str | None = None


class AccountSettingsUpdateRequest(BaseModel):
    # Integrações
    chatnexo_base_url: str | None = None
    chatnexo_api_key: str | None = None
    chatnexo_account_id: int | None = None
    chatnexo_inbox_id: int | None = None
    hubla_webhook_secret: str | None = None
    meta_api_key: str | None = None
    meta_waba_id: str | None = None
    meta_app_id: str | None = None
    alert_whatsapp_target: str | None = None
    # Comportamento
    idle_ping_minutes: int | None = None
    idle_close_minutes: int | None = None
    intent_confidence_threshold: float | None = None
    message_buffer_wait_seconds: int | None = None
    refund_deadline_days: int | None = None
    welcome_d1_delay_hours: int | None = None
    ai_memory_messages: int | None = Field(default=None, ge=5, le=100)
    # Message Buffer
    message_buffer_enabled: bool | None = None
    message_buffer_outgoing_url: str | None = None
    message_buffer_api_key: str | None = None
    message_buffer_tenant_id: str | None = None
