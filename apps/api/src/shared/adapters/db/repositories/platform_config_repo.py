from __future__ import annotations

import uuid
from dataclasses import dataclass

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.adapters.db.models import PlatformConfigModel
from shared.config.settings import get_settings
from shared.domain.entities.platform_config import PlatformConfig


@dataclass
class PlatformConfigRepository:
    session: AsyncSession

    def _fernet(self) -> Fernet:
        k = get_settings().integration_credentials_key
        return Fernet(k.encode() if isinstance(k, str) else k)

    def encrypt(self, plaintext: str) -> str:
        return self._fernet().encrypt(plaintext.encode()).decode()

    def decrypt(self, token: str | None) -> str | None:
        # Degrada para None em blob inválido / key divergente, em vez de propagar
        # InvalidToken. Isso preserva o fallback de env do resolve_openai_key e
        # evita derrubar runtime caso o backfill copie um blob corrompido.
        if not token:
            return None
        try:
            return self._fernet().decrypt(token.encode()).decode()
        except InvalidToken:
            return None

    async def get(self) -> PlatformConfig:
        m = (await self.session.execute(select(PlatformConfigModel).limit(1))).scalar_one_or_none()
        if m is None:
            return PlatformConfig()
        return PlatformConfig(
            openai_api_key=m.openai_api_key,
            smtp_host=m.smtp_host,
            smtp_port=m.smtp_port,
            smtp_use_tls=m.smtp_use_tls,
            smtp_username=m.smtp_username,
            smtp_encrypted_password=m.smtp_encrypted_password,
            smtp_from_name=m.smtp_from_name,
            smtp_from_email=m.smtp_from_email,
        )

    async def upsert(self, **fields) -> PlatformConfig:
        m = (await self.session.execute(select(PlatformConfigModel).limit(1))).scalar_one_or_none()
        if m is None:
            m = PlatformConfigModel(id=uuid.uuid4(), singleton=True)
            self.session.add(m)
        for k, v in fields.items():
            if v is not None:
                setattr(m, k, v)
        await self.session.flush()
        return await self.get()
