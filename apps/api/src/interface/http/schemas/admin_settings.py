# apps/api/src/interface/http/schemas/admin_settings.py
from __future__ import annotations

from pydantic import BaseModel


class AccountSettingsResponse(BaseModel):
    # Integrações
    chatnexo_base_url: str
    chatnexo_api_key: str
    hubla_webhook_secret: str
    cademi_api_url: str
    cademi_api_key: str
    cademi_max_retries: int
    cademi_retry_base_seconds: float
    openai_api_key: str
    meta_api_key: str
    # Comportamento
    idle_ping_minutes: int
    idle_close_minutes: int
    intent_confidence_threshold: float
    message_buffer_wait_seconds: int
    refund_deadline_days: int
    welcome_d1_delay_hours: int
    loja_express_d1_delay_hours: int
    loja_express_d3_delay_hours: int
    loja_express_d5_delay_hours: int
    loja_express_d7_delay_hours: int


class AccountSettingsUpdateRequest(BaseModel):
    # Integrações
    chatnexo_base_url: str | None = None
    chatnexo_api_key: str | None = None
    hubla_webhook_secret: str | None = None
    cademi_api_url: str | None = None
    cademi_api_key: str | None = None
    cademi_max_retries: int | None = None
    cademi_retry_base_seconds: float | None = None
    openai_api_key: str | None = None
    meta_api_key: str | None = None
    # Comportamento
    idle_ping_minutes: int | None = None
    idle_close_minutes: int | None = None
    intent_confidence_threshold: float | None = None
    message_buffer_wait_seconds: int | None = None
    refund_deadline_days: int | None = None
    welcome_d1_delay_hours: int | None = None
    loja_express_d1_delay_hours: int | None = None
    loja_express_d3_delay_hours: int | None = None
    loja_express_d5_delay_hours: int | None = None
    loja_express_d7_delay_hours: int | None = None
