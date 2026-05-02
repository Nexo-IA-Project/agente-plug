from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.adapters.db.models import ConversationModel
from shared.adapters.db.repositories.base import require_account_id
from shared.domain.entities.conversation import (
    Conversation,
    ConversationStatus,
    IdleState,
)


def _to_entity(model: ConversationModel) -> Conversation:
    return Conversation(
        id=model.id,
        account_id=model.account_id,
        contact_id=model.contact_id,
        chatnexo_conversation_id=model.chatnexo_conversation_id,
        status=ConversationStatus(model.status),
        last_activity_at=model.last_activity_at,
        window_expires_at=model.window_expires_at,
        handoff_reason=model.handoff_reason,
        idle_state=IdleState(model.idle_state),
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


@dataclass
class ConversationRepository:
    session: AsyncSession

    async def get_by_chatnexo_id(
        self, *, account_id: UUID, chatnexo_conversation_id: int
    ) -> Conversation | None:
        require_account_id(account_id)
        stmt = select(ConversationModel).where(
            ConversationModel.account_id == account_id,
            ConversationModel.chatnexo_conversation_id == chatnexo_conversation_id,
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        return _to_entity(model) if model else None

    async def create(self, conv: Conversation) -> Conversation:
        require_account_id(conv.account_id)
        model = ConversationModel(
            id=conv.id,
            account_id=conv.account_id,
            contact_id=conv.contact_id,
            chatnexo_conversation_id=conv.chatnexo_conversation_id,
            status=conv.status.value,
            last_activity_at=conv.last_activity_at,
            window_expires_at=conv.window_expires_at,
            handoff_reason=conv.handoff_reason,
            idle_state=conv.idle_state.value,
        )
        self.session.add(model)
        await self.session.flush()
        return _to_entity(model)

    async def update_status(
        self,
        *,
        account_id: UUID,
        conversation_id: UUID,
        status: ConversationStatus,
        handoff_reason: str | None = None,
    ) -> None:
        require_account_id(account_id)
        stmt = select(ConversationModel).where(
            ConversationModel.account_id == account_id,
            ConversationModel.id == conversation_id,
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one()
        model.status = status.value
        if handoff_reason is not None:
            model.handoff_reason = handoff_reason

    async def touch_activity(
        self, *, account_id: UUID, conversation_id: UUID, at: datetime
    ) -> None:
        require_account_id(account_id)
        stmt = select(ConversationModel).where(
            ConversationModel.account_id == account_id,
            ConversationModel.id == conversation_id,
        )
        model = (await self.session.execute(stmt)).scalar_one()
        model.last_activity_at = at
