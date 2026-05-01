# tests/unit/config/test_settings_refund.py
from nexoia.config.settings import Settings


def test_refund_deadline_days_default():
    s = Settings(
        database_url="postgresql+asyncpg://x:x@localhost/x",
        redis_url="redis://localhost",
        openai_api_key="sk-x",
        chatnexo_base_url="http://x",
        chatnexo_api_key="x",
        hubla_webhook_secret="x",
        admin_api_key="x",
        meta_api_key="x",
        integration_credentials_key="x" * 32,
    )
    assert s.refund_deadline_days == 7
    assert s.refund_mutex_ttl_seconds == 3600
