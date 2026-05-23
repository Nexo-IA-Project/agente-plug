"""Resolver de account single-tenant.

Enquanto multi-tenancy não chega, o sistema opera com um único account.
Em vez de uma constante UUID hardcoded (que não bate com o seed real do DB),
buscamos o primeiro account criado e cacheamos em memória para o resto do
processo. Determinístico (ORDER BY created_at), idempotente, single source
of truth para todos os routers/handlers admin.

Quando multi-tenant for ativado, este módulo é o ponto único de mudança:
deve passar a receber `auth.account_id` ou um identificador do request.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.adapters.db.models import AccountModel

_cached_account_uuid: UUID | None = None

# UUID sentinel apenas para fallback de testes unitários que não tocam o DB.
# Produção SEMPRE usa get_default_account_uuid(session). Não persistir esta UUID
# no DB — não existe row com este ID.
DEFAULT_ACCOUNT_UUID: UUID = UUID("00000000-0000-0000-0000-000000000001")


async def get_default_account_uuid(session: AsyncSession) -> UUID:
    """Retorna o UUID do primeiro account (single-tenant), cacheado.

    Lança RuntimeError se nenhum account existir — situação só esperada
    em DB recém-criado antes do seed inicial.
    """
    global _cached_account_uuid
    if _cached_account_uuid is not None:
        return _cached_account_uuid

    result = await session.execute(
        select(AccountModel.id).order_by(AccountModel.created_at).limit(1)
    )
    row: UUID | None = result.scalar_one_or_none()
    if row is None:
        raise RuntimeError(
            "Nenhuma account encontrada — rode a migration de seed inicial primeiro."
        )
    _cached_account_uuid = row
    return row


def reset_cache() -> None:
    """Limpa o cache — usado em testes que recriam o DB."""
    global _cached_account_uuid
    _cached_account_uuid = None
