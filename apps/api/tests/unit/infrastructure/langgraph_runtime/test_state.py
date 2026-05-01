from __future__ import annotations

from uuid import uuid4

from langchain_core.messages import HumanMessage

from shared.domain.value_objects.intent import Intent
from shared.domain.value_objects.sentiment import Sentiment
from agent.state import (
    AgentState,
    ConversationState,
    make_initial_state,
)


# ---------------------------------------------------------------------------
# New AgentState tests (Core v2)
# ---------------------------------------------------------------------------


def test_agent_state_has_messages_field() -> None:
    state: AgentState = {
        "messages": [HumanMessage("oi")],
        "skill_em_andamento": None,
        "mensagens_pendentes": [],
    }
    assert len(state["messages"]) == 1


def test_agent_state_skill_em_andamento_optional() -> None:
    state: AgentState = {
        "messages": [],
        "skill_em_andamento": None,
        "mensagens_pendentes": [],
    }
    assert state["skill_em_andamento"] is None


def test_agent_state_mensagens_pendentes_list() -> None:
    state: AgentState = {
        "messages": [],
        "skill_em_andamento": "buscar_aluno_cademi",
        "mensagens_pendentes": ["msg1"],
    }
    assert state["mensagens_pendentes"] == ["msg1"]


# ---------------------------------------------------------------------------
# Legacy ConversationState tests (kept until Task 16 deletes old pipeline)
# ---------------------------------------------------------------------------


def test_make_initial_state_defaults() -> None:
    state = make_initial_state(
        correlation_id="corr-1",
        account_id=uuid4(),
        conversation_id=uuid4(),
        incoming_text="olá",
    )
    assert state["messages"][-1]["content"] == "olá"
    assert state["intent"] is None
    assert state["sentiment"] == Sentiment.NEUTRAL.value
    assert state["handoff_requested"] is False
    assert state["attempts"] == 0
    assert state["capability_state"] == {}


def test_state_is_typed_dict() -> None:
    state: ConversationState = {
        "correlation_id": "c",
        "account_id": "a",
        "conversation_id": "cv",
        "messages": [],
        "intent": Intent.ACCESS.value,
        "sentiment": Sentiment.NEUTRAL.value,
        "handoff_requested": False,
        "attempts": 0,
        "capability_state": {},
    }
    assert state["intent"] == "access"
