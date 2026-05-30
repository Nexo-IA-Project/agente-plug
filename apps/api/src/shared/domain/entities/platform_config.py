from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PlatformConfig:
    openai_api_key: str | None = None
    smtp_host: str | None = None
    smtp_port: int | None = None
    smtp_use_tls: bool = True
    smtp_username: str | None = None
    smtp_encrypted_password: str | None = None
    smtp_from_name: str | None = None
    smtp_from_email: str | None = None
