import pytest

from shared.config.settings import Settings


def test_cademi_and_welcome_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    env = {
        "DATABASE_URL": "postgresql+asyncpg://u:p@localhost/db",
        "REDIS_URL": "redis://localhost:6379",
        "CHATNEXO_BASE_URL": "http://localhost:4000",
        "CHATNEXO_API_KEY": "key",
        "OPENAI_API_KEY": "sk-test",
        "HUBLA_WEBHOOK_SECRET": "secret",
        "ADMIN_API_KEY": "admin",
        "META_API_KEY": "meta",
        "INTEGRATION_CREDENTIALS_KEY": "YEqfuO1aT0ibxW5p3oACqKm4sVqlKwpz9wZ0qCc0Yfs=",
    }
    for k, v in env.items():
        monkeypatch.setenv(k, v)

    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.cademi_api_url == ""
    assert s.cademi_api_key == ""
    assert s.cademi_max_retries == 3
    assert s.cademi_retry_base_seconds == 1.0
    assert s.message_buffer_wait_seconds == 0
    assert s.welcome_check_delay_hours == 1
    assert s.welcome_d1_delay_hours == 24
