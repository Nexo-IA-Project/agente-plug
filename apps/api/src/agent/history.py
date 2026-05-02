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

    async def load(self, thread_id: str) -> list[Message]:
        """Return the stored messages for *thread_id*, or [] if none exist."""
        stmt = select(ConversationMessageModel).where(
            ConversationMessageModel.thread_id == thread_id
        )
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        return list(row.messages) if row else []

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
