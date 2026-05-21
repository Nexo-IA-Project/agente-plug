"""ConversationHistory — persists the OpenAI message list for a thread in PostgreSQL."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from shared.adapters.db.models import ConversationMessageModel

Message = dict[str, Any]


@dataclass
class ConversationHistory:
    """Load, save, and clear the OpenAI message list for a given thread_id.

    One row per thread — upsert on save, hard-delete on clear.
    """

    session: AsyncSession

    async def load(self, thread_id: str, limit: int | None = None) -> list[Message]:
        """Return stored messages for *thread_id*.

        Se ``limit`` for informado, retorna apenas as últimas ``limit`` mensagens.
        O storage persiste sempre o histórico completo — ``limit`` não trunca o JSONB.
        """
        stmt = select(ConversationMessageModel).where(
            ConversationMessageModel.thread_id == thread_id
        )
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return []
        messages = list(row.messages)
        if limit is not None and len(messages) > limit:
            return messages[-limit:]
        return messages

    async def save(self, thread_id: str, messages: list[Message]) -> None:
        """Upsert *messages* for *thread_id*."""
        stmt = (
            pg_insert(ConversationMessageModel)
            .values(thread_id=thread_id, messages=messages)
            .on_conflict_do_update(
                index_elements=["thread_id"],
                set_={"messages": messages, "updated_at": func.now()},
            )
        )
        await self.session.execute(stmt)

    async def clear(self, thread_id: str) -> None:
        """Delete the message history for *thread_id*."""
        stmt = delete(ConversationMessageModel).where(
            ConversationMessageModel.thread_id == thread_id
        )
        await self.session.execute(stmt)
