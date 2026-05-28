# apps/api/src/shared/adapters/email/smtp_email_service.py
from __future__ import annotations

from email.message import EmailMessage

import aiosmtplib

from shared.adapters.db.repositories.smtp_config_repo import SmtpConfigRepository


class SmtpNotConfiguredError(Exception):
    """SMTP config absent for the given account."""


class SmtpEmailService:
    def __init__(self, repo: SmtpConfigRepository) -> None:
        self._repo = repo

    async def send_email(self, account_id: int, to: str, subject: str, body_html: str) -> None:
        cfg = await self._repo.get(account_id=account_id)
        if cfg is None:
            raise SmtpNotConfiguredError(f"SMTP not configured for account {account_id}")

        password = self._repo.decrypt_password(cfg.encrypted_password)

        msg = EmailMessage()
        msg["From"] = f"{cfg.from_name} <{cfg.from_email}>"
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content("HTML email — abra em um cliente compatível.")
        msg.add_alternative(body_html, subtype="html")

        # use_tls=True → SMTPS (implicit TLS, port 465)
        # start_tls=True → STARTTLS (explicit, port 587)
        # Convention: use_tls in config means STARTTLS (port 587)
        await aiosmtplib.send(
            msg,
            hostname=cfg.host,
            port=cfg.port,
            username=cfg.username,
            password=password,
            use_tls=False,
            start_tls=cfg.use_tls,
        )
