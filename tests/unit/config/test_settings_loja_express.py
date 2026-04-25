# tests/unit/config/test_settings_loja_express.py
from nexoia.config.settings import Settings


def _make_settings(**overrides) -> Settings:
    defaults = {
        "database_url": "postgresql+asyncpg://x:x@localhost/x",
        "redis_url": "redis://localhost",
        "openai_api_key": "sk-x",
        "chatnexo_base_url": "http://x",
        "chatnexo_api_key": "x",
        "hubla_webhook_secret": "x",
        "admin_api_key": "x",
        "meta_api_key": "x",
        "integration_credentials_key": "x" * 32,
    }
    defaults.update(overrides)
    return Settings(**defaults)


def test_loja_express_product_tags_default():
    s = _make_settings()
    assert s.loja_express_product_tags == ["loja_express", "loja-express"]


def test_loja_express_d1_delay_hours_default():
    s = _make_settings()
    assert s.loja_express_d1_delay_hours == 24


def test_loja_express_d3_delay_hours_default():
    s = _make_settings()
    assert s.loja_express_d3_delay_hours == 72


def test_loja_express_d5_delay_hours_default():
    s = _make_settings()
    assert s.loja_express_d5_delay_hours == 120


def test_loja_express_d7_delay_hours_default():
    s = _make_settings()
    assert s.loja_express_d7_delay_hours == 168
