# apps/api/src/shared/adapters/email/smtp_email_service.py
from __future__ import annotations

from email.message import EmailMessage

import aiosmtplib

from shared.adapters.db.repositories.platform_config_repo import PlatformConfigRepository


class SmtpNotConfiguredError(Exception):
    """SMTP config absent in the global platform config."""


class SmtpEmailService:
    def __init__(self, repo: PlatformConfigRepository) -> None:
        self._repo = repo

    async def send_email(self, *, to: str, subject: str, body_html: str) -> None:
        cfg = await self._repo.get()
        if not cfg.smtp_host:
            raise SmtpNotConfiguredError("SMTP not configured")

        password = self._repo.decrypt(cfg.smtp_encrypted_password)

        msg = EmailMessage()
        msg["From"] = f"{cfg.smtp_from_name} <{cfg.smtp_from_email}>"
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content("HTML email — abra em um cliente compatível.")
        msg.add_alternative(body_html, subtype="html")

        # use_tls=True → SMTPS (implicit TLS, port 465)
        # start_tls=True → STARTTLS (explicit, port 587)
        # Convention: smtp_use_tls in config means STARTTLS (port 587)
        await aiosmtplib.send(
            msg,
            hostname=cfg.smtp_host,
            port=cfg.smtp_port,
            username=cfg.smtp_username,
            password=password,
            use_tls=False,
            start_tls=cfg.smtp_use_tls,
        )
