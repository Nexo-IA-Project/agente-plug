from __future__ import annotations

from typing import Any, TypedDict
from uuid import UUID

from nexoia.domain.value_objects.sentiment import Sentiment


class MessageEnvelope(TypedDict):
    role: str
    content: str


class ConversationState(TypedDict, total=False):
    correlation_id: str
    account_id: str
    conversation_id: str
    messages: list[MessageEnvelope]
    intent: str | None
    sentiment: str
    handoff_requested: bool
    attempts: int
    capability_state: dict[str, Any]


def make_initial_state(
    *,
    correlation_id: str,
    account_id: UUID,
    conversation_id: UUID,
    incoming_text: str,
) -> ConversationState:
    return {
        "correlation_id": correlation_id,
        "account_id": str(account_id),
        "conversation_id": str(conversation_id),
        "messages": [{"role": "user", "content": incoming_text}],
        "intent": None,
        "sentiment": Sentiment.NEUTRAL.value,
        "handoff_requested": False,
        "attempts": 0,
        "capability_state": {},
    }
