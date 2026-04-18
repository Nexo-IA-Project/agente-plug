from uuid import uuid4

from nexoia.domain.value_objects.intent import Intent
from nexoia.domain.value_objects.sentiment import Sentiment
from nexoia.infrastructure.langgraph_runtime.state import (
    ConversationState,
    make_initial_state,
)


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
