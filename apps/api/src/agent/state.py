from __future__ import annotations

from typing import Any
from uuid import UUID

from langgraph.graph import MessagesState

from nexoia.domain.value_objects.sentiment import Sentiment


class AgentState(MessagesState):
    """Estado do loop LLM-orquestrado.

    - messages: herdado de MessagesState — lista de HumanMessage/AIMessage/ToolMessage
    - skill_em_andamento: nome do @tool em execução; None quando livre
    - mensagens_pendentes: textos que chegaram enquanto skill_em_andamento != None

    account_id, phone, conversation_id viajam no RunnableConfig, nunca aqui.
    """

    skill_em_andamento: str | None
    mensagens_pendentes: list[str]


# ---------------------------------------------------------------------------
# Deprecated aliases — remove when Task 16 deletes old pipeline
# ---------------------------------------------------------------------------

class MessageEnvelope(dict):  # type: ignore[type-arg]
    """Deprecated: role/content dict used by the old ConversationState pipeline."""

    role: str
    content: str


# ConversationState kept as a TypedDict alias so graph_builder.py and
# existing tests continue to work without modification.
from typing import TypedDict  # noqa: E402


class ConversationState(TypedDict, total=False):
    """Deprecated: old LangGraph state. Replaced by AgentState in Core v2."""

    correlation_id: str
    account_id: str
    conversation_id: str
    messages: list[Any]
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
    """Deprecated: factory for old ConversationState. Remove in Task 16."""
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
