from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    database_url: str
    redis_url: str
    openai_api_key: str
    chatnexo_base_url: str
    chatnexo_api_key: str
    hubla_webhook_secret: str
    admin_api_key: str
    meta_api_key: str
    integration_credentials_key: str

    enable_priority_queue: bool = False
    log_level: str = "INFO"
    sentry_dsn: str | None = None
    idle_ping_minutes: int = Field(default=30, ge=1)
    idle_close_minutes: int = Field(default=20, ge=1)
    intent_confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0)

    # Cademi API
    cademi_api_url: str = ""
    cademi_api_key: str = ""
    cademi_max_retries: int = 3
    cademi_retry_base_seconds: float = 1.0

    # Capability Welcome
    welcome_check_delay_hours: int = 1
    welcome_d1_delay_hours: int = 24
    message_buffer_wait_seconds: int = 0

    # Capability Refund
    refund_deadline_days: int = 7
    refund_mutex_ttl_seconds: int = 3600


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
