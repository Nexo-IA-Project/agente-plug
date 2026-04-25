# tests/unit/infrastructure/langgraph_runtime/test_graph_builder.py
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from nexoia.infrastructure.langgraph_runtime.graph_builder import build_graph


def test_build_graph_returns_compiled_graph():
    graph = build_graph(
        access_repo=AsyncMock(),
        cademi=AsyncMock(),
        chatnexo=AsyncMock(),
        guard_service=MagicMock(),
        long_term_repo=AsyncMock(),
        llm=AsyncMock(),
        capability_repo=AsyncMock(),
        memory_extractor=AsyncMock(),
        refund_repo=AsyncMock(),
        hubla=AsyncMock(),
        legal_history=AsyncMock(),
        refund_mutex=AsyncMock(),
        knowledge_repo=AsyncMock(),
        usage_log_repo=AsyncMock(),
        checkpointer=None,
    )
    assert graph is not None


def test_build_graph_nodes_include_raciocinar_executar_pos_execucao():
    graph = build_graph(
        access_repo=AsyncMock(),
        cademi=AsyncMock(),
        chatnexo=AsyncMock(),
        guard_service=MagicMock(),
        long_term_repo=AsyncMock(),
        llm=AsyncMock(),
        capability_repo=AsyncMock(),
        memory_extractor=AsyncMock(),
        refund_repo=AsyncMock(),
        hubla=AsyncMock(),
        legal_history=AsyncMock(),
        refund_mutex=AsyncMock(),
        knowledge_repo=AsyncMock(),
        usage_log_repo=AsyncMock(),
        checkpointer=None,
    )
    node_names = set(graph.nodes.keys())
    assert "raciocinar" in node_names
    assert "executar" in node_names
    assert "pos_execucao" in node_names


def test_build_graph_accepts_refund_params():
    """build_graph deve aceitar refund_repo, hubla, legal_history, refund_mutex."""
    from unittest.mock import AsyncMock

    from nexoia.infrastructure.langgraph_runtime.graph_builder import build_graph
    graph = build_graph(
        access_repo=AsyncMock(),
        cademi=AsyncMock(),
        chatnexo=AsyncMock(),
        guard_service=AsyncMock(),
        long_term_repo=AsyncMock(),
        llm=AsyncMock(),
        capability_repo=AsyncMock(),
        memory_extractor=AsyncMock(),
        refund_repo=AsyncMock(),
        hubla=AsyncMock(),
        legal_history=AsyncMock(),
        refund_mutex=AsyncMock(),
        knowledge_repo=AsyncMock(),
        usage_log_repo=AsyncMock(),
        checkpointer=None,
    )
    assert graph is not None
