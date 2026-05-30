from __future__ import annotations

from uuid import UUID

from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.adapters.db.models import SmtpConfigModel
from shared.config.settings import get_settings
from shared.domain.entities.smtp_config import SmtpConfig


def _to_entity(m: SmtpConfigModel) -> SmtpConfig:
    return SmtpConfig(
        id=m.id,
        account_id=m.account_id,
        host=m.host,
        port=m.port,
        username=m.username,
        encrypted_password=m.encrypted_password,
        use_tls=m.use_tls,
        from_name=m.from_name,
        from_email=m.from_email,
        updated_at=m.updated_at,
    )


class SmtpConfigRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        key = get_settings().integration_credentials_key
        self._fernet = Fernet(key.encode() if isinstance(key, str) else key)

    def encrypt_password(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt_password(self, encrypted: str) -> str:
        return self._fernet.decrypt(encrypted.encode()).decode()

    async def get(self, account_id: UUID) -> SmtpConfig | None:
        result = await self._session.execute(
            select(SmtpConfigModel).where(SmtpConfigModel.account_id == account_id)
        )
        row = result.scalar_one_or_none()
        return _to_entity(row) if row else None

    async def upsert(
        self,
        account_id: UUID,
        host: str,
        port: int,
        username: str,
        password_plaintext: str,
        use_tls: bool,
        from_name: str,
        from_email: str,
    ) -> SmtpConfig:
        encrypted = self.encrypt_password(password_plaintext)

        result = await self._session.execute(
            select(SmtpConfigModel).where(SmtpConfigModel.account_id == account_id)
        )
        m = result.scalar_one_or_none()
        if m is None:
            m = SmtpConfigModel(
                account_id=account_id,
                host=host,
                port=port,
                username=username,
                encrypted_password=encrypted,
                use_tls=use_tls,
                from_name=from_name,
                from_email=from_email,
            )
            self._session.add(m)
        else:
            m.host = host
            m.port = port
            m.username = username
            m.encrypted_password = encrypted
            m.use_tls = use_tls
            m.from_name = from_name
            m.from_email = from_email
        await self._session.flush()
        return _to_entity(m)
