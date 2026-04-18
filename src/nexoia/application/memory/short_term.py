from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from langgraph.checkpoint.base import BaseCheckpointSaver


@dataclass
class ShortTermMemory:
    """Thin wrapper over LangGraph checkpoint for convenience queries."""

    checkpointer: BaseCheckpointSaver

    def thread_id(self, *, account_id: UUID, conversation_id: UUID) -> str:
        return f"{account_id}:{conversation_id}"

    async def last_checkpoint(
        self, *, account_id: UUID, conversation_id: UUID
    ) -> dict[str, Any] | None:
        tid = self.thread_id(account_id=account_id, conversation_id=conversation_id)
        config = {"configurable": {"thread_id": tid}}
        tuple_ = await self.checkpointer.aget_tuple(config)
        return tuple_.checkpoint if tuple_ else None
