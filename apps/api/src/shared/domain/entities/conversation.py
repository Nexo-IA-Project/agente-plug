from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class ConversationStatus(StrEnum):
    ACTIVE = "active"
    IDLE_PINGED = "idle_pinged"
    CLOSED_BY_TIMEOUT = "closed_by_timeout"
    HANDED_OFF = "handed_off"
    RESOLVED = "resolved"


class IdleState(StrEnum):
    NONE = "none"
    PING_SENT = "ping_sent"
    CLOSED = "closed"


@dataclass(slots=True)
class Conversation:
    id: UUID
    account_id: UUID
    contact_id: UUID
    chatnexo_conversation_id: int
    status: ConversationStatus
    last_activity_at: datetime
    window_expires_at: datetime
    handoff_reason: str | None = None
    idle_state: IdleState = IdleState.NONE
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def is_inside_meta_window(self, *, now: datetime) -> bool:
        return now <= self.window_expires_at

    def can_send_free_text(self, *, now: datetime) -> bool:
        return self.status in {
            ConversationStatus.ACTIVE,
            ConversationStatus.IDLE_PINGED,
        } and self.is_inside_meta_window(now=now)

    def mark_handed_off(self, *, reason: str) -> None:
        self.status = ConversationStatus.HANDED_OFF
        self.handoff_reason = reason

    def mark_resolved(self) -> None:
        self.status = ConversationStatus.RESOLVED

    def mark_closed_by_timeout(self) -> None:
        self.status = ConversationStatus.CLOSED_BY_TIMEOUT
        self.idle_state = IdleState.CLOSED
