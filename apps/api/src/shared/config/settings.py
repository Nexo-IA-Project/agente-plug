from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve caminhos absolutos para encontrar .env.local independente do cwd
_API_DIR = Path(__file__).parent.parent.parent.parent  # apps/api/
_REPO_ROOT = _API_DIR.parent.parent  # raiz do monorepo


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(
            str(_API_DIR / ".env.local"),
            str(_REPO_ROOT / ".env.local"),
            str(_API_DIR / ".env"),
            str(_REPO_ROOT / ".env"),
        ),
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
    meta_waba_id: str = ""
    integration_credentials_key: str

    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
    ]
    cors_origin_regex: str | None = None

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

    # Capability Loja Express
    loja_express_product_tags: list[str] = ["loja_express", "loja-express"]
    loja_express_d1_delay_hours: int = 24
    loja_express_d3_delay_hours: int = 72
    loja_express_d5_delay_hours: int = 120
    loja_express_d7_delay_hours: int = 168

    # KB Admin
    kb_chunk_size: int = 512
    kb_chunk_overlap: int = 50
    kb_top_k: int = Field(default=5, ge=1)
    kb_threshold: float = 0.55
    kb_embedding_model: str = "text-embedding-3-small"
    kb_max_file_size_mb: int = 20

    # Capability Knowledge (RAG)
    kb_attempt_1_threshold: float = Field(default=0.55, ge=0.0, le=1.0)

    # JWT — deve ser configurado via JWT_SECRET no ambiente (sem valor padrão)
    jwt_secret: str
    jwt_expire_minutes: int = 60


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
