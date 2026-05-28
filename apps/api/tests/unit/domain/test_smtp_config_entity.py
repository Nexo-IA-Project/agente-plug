from __future__ import annotations

from shared.domain.entities.smtp_config import SmtpConfig


def test_smtp_config_creation():
    cfg = SmtpConfig(
        account_id=1,
        host="smtp.gmail.com",
        port=587,
        username="bot@example.com",
        encrypted_password="gAAAAA...",
        use_tls=True,
        from_name="NexoIA",
        from_email="bot@example.com",
    )
    assert cfg.host == "smtp.gmail.com"
    assert cfg.port == 587
    assert cfg.use_tls is True
    assert isinstance(cfg.id, str)
