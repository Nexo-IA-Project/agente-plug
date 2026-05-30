from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from shared.adapters.db.repositories.platform_config_repo import PlatformConfigRepository
from shared.config.settings import get_settings


async def resolve_openai_key(session: AsyncSession) -> str:
    """Resolve a chave OpenAI a partir da config GLOBAL (platform_config).

    Lê o `PlatformConfig` global, decifra `openai_api_key`. Se vazio, faz
    fallback para `get_settings().openai_api_key` (env). Retorna texto puro.
    """
    repo = PlatformConfigRepository(session=session)
    config = await repo.get()
    decrypted = repo.decrypt(config.openai_api_key)
    if decrypted:
        return decrypted
    return get_settings().openai_api_key
