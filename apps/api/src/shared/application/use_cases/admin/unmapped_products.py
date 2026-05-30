"""Use cases para "Pendências" — produtos Hubla não reconhecidos (Task 7).

Um produto fica "pendente" quando um evento Hubla chega com um `hubla_product_id`
que não casa nenhum produto cadastrado (nem por id/alias, nem por nome exato). O
lead correspondente é marcado com `product_unmatched=True`.

Três operações:
  - list_unmapped: agrupa os leads pendentes por hubla_product_id.
  - resolve: cria um alias (hubla_id → product_id), tornando o produto reconhecível.
  - reprocess: re-enfileira os hubla_events afetados para o pipeline rodar de novo
    (agora casando o produto via alias). Suporta schedule_mode para escolher entre
    re-agendar os steps a partir de agora ("from_now") ou usar o horário original.
"""

from __future__ import annotations

import uuid as _uuid_module
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.adapters.db.models import (
    HublaEventModel,
    JobQueueModel,
    ProductHublaAliasModel,
)
from shared.domain.value_objects.priority import Priority


async def list_unmapped(account_id: UUID, lead_repo: Any) -> list[dict]:
    """Lista grupos de pendências (produtos não reconhecidos) por hubla_product_id."""
    return await lead_repo.list_unmapped(account_id)


async def resolve(
    *,
    account_id: UUID,
    hubla_product_id: str,
    product_id: UUID,
    product_repo: Any,
    lead_repo: Any,
) -> dict[str, int]:
    """Associa um hubla_product_id a um produto existente (cria alias).

    Idempotente: se o alias já existir para (account_id, hubla_id), não cria de
    novo (evita IntegrityError no unique e rollback da sessão compartilhada).
    """
    session: AsyncSession = product_repo.session
    existing = (
        await session.execute(
            select(ProductHublaAliasModel.id).where(
                ProductHublaAliasModel.account_id == account_id,
                ProductHublaAliasModel.hubla_id == hubla_product_id,
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        await product_repo.add_alias(
            account_id=account_id,
            product_id=product_id,
            hubla_id=hubla_product_id,
        )

    affected = await lead_repo.count_unmapped_by_product(account_id, hubla_product_id)
    return {"affected_leads": affected}


async def reprocess(
    *,
    account_id: UUID,
    hubla_product_id: str,
    schedule_mode: Literal["from_now", "original"],
    session: AsyncSession,
) -> dict[str, int]:
    """Re-enfileira os hubla_events do produto pendente para reprocessamento.

    Outbox pattern: os jobs são inseridos na MESMA session da requisição (commit
    atômico via session_scope). Cada job carrega `_schedule_mode` no payload para
    o handler decidir como agendar os steps.
    """
    stmt = select(HublaEventModel).where(
        HublaEventModel.account_id == account_id,
        HublaEventModel.hubla_product_id == hubla_product_id,
    )
    events = (await session.execute(stmt)).scalars().all()

    enqueued = 0
    for evt in events:
        payload = {**evt.payload, "_schedule_mode": schedule_mode}
        session.add(
            JobQueueModel(
                id=_uuid_module.uuid4(),
                kind="hubla_event",
                payload=payload,
                attempt=1,
                last_error=None,
                priority=Priority.NORMAL.score,
            )
        )
        enqueued += 1

    await session.flush()
    return {"enqueued": enqueued}
