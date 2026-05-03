# tests/unit/test_kb_settings.py
from shared.config.settings import Settings


def test_kb_settings_defaults():
    # Settings with minimal required fields (env vars mocked via kwargs)
    s = Settings(
        database_url="postgresql+asyncpg://x:x@localhost/x",
        redis_url="redis://localhost",
        openai_api_key="sk-test",
        chatnexo_base_url="https://chatnexo.example.com",
        chatnexo_api_key="cnx-key",
        hubla_webhook_secret="secret",
        admin_api_key="admin-key",
        meta_api_key="meta-key",
        integration_credentials_key="cred-key",
        jwt_secret="test-jwt-secret-with-enough-entropy-xxxxx",
    )
    assert s.kb_chunk_size == 512
    assert s.kb_chunk_overlap == 50
    assert s.kb_top_k == 5
    assert s.kb_threshold == 0.55
    assert s.kb_embedding_model == "text-embedding-3-small"
    assert s.kb_max_file_size_mb == 20
    assert s.jwt_secret == "test-jwt-secret-with-enough-entropy-xxxxx"
    assert s.jwt_expire_minutes == 60
