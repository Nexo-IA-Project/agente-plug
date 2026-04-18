from __future__ import annotations

from typing import Any, Callable

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph

from nexoia.infrastructure.langgraph_runtime.state import ConversationState


def build_main_graph(
    *,
    checkpointer: BaseCheckpointSaver,
    context_builder: Callable[[ConversationState], ConversationState],
    sentiment_detector: Callable[[ConversationState], ConversationState],
    intent_router: Callable[[ConversationState], ConversationState],
    dispatch: Callable[[ConversationState], str],
    capability_runner: Callable[[ConversationState], ConversationState],
    response_publisher: Callable[[ConversationState], ConversationState],
    memory_saver: Callable[[ConversationState], ConversationState],
) -> Any:
    graph = StateGraph(ConversationState)

    graph.add_node("context_builder", context_builder)
    graph.add_node("sentiment", sentiment_detector)
    graph.add_node("intent_router", intent_router)
    graph.add_node("capability", capability_runner)
    graph.add_node("response", response_publisher)
    graph.add_node("save_memory", memory_saver)

    graph.add_edge(START, "context_builder")
    graph.add_edge("context_builder", "sentiment")
    graph.add_edge("sentiment", "intent_router")
    graph.add_conditional_edges(
        "intent_router",
        dispatch,
        {"capability": "capability", "handoff": "save_memory"},
    )
    graph.add_edge("capability", "response")
    graph.add_edge("response", "save_memory")
    graph.add_edge("save_memory", END)

    return graph.compile(checkpointer=checkpointer)
