import pytest

from nexoia.config.settings import Settings


def test_settings_load_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    env = {
        "DATABASE_URL": "postgresql+asyncpg://u:p@host:5432/db",
        "REDIS_URL": "redis://host:6379/0",
        "OPENAI_API_KEY": "sk-test",
        "CHATNEXO_BASE_URL": "http://localhost:4000",
        "CHATNEXO_API_KEY": "cn-key",
        "HUBLA_WEBHOOK_SECRET": "hubla-secret",
        "ADMIN_API_KEY": "admin-key",
        "META_API_KEY": "meta-key",
        "INTEGRATION_CREDENTIALS_KEY": "YEqfuO1aT0ibxW5p3oACqKm4sVqlKwpz9wZ0qCc0Yfs=",
    }
    for k, v in env.items():
        monkeypatch.setenv(k, v)

    settings = Settings()

    assert settings.database_url == env["DATABASE_URL"]
    assert settings.enable_priority_queue is False
    assert settings.idle_ping_minutes == 30
    assert settings.idle_close_minutes == 20
    assert settings.intent_confidence_threshold == 0.7
    assert settings.log_level == "INFO"


def test_settings_missing_required_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("CHATNEXO_BASE_URL", raising=False)
    monkeypatch.delenv("CHATNEXO_API_KEY", raising=False)
    monkeypatch.delenv("HUBLA_WEBHOOK_SECRET", raising=False)
    monkeypatch.delenv("ADMIN_API_KEY", raising=False)
    monkeypatch.delenv("META_API_KEY", raising=False)
    monkeypatch.delenv("INTEGRATION_CREDENTIALS_KEY", raising=False)
    # Pass _env_file=None to prevent loading from .env on disk
    with pytest.raises(Exception):
        Settings(_env_file=None)  # type: ignore[call-arg]
