# tests/unit/infrastructure/langgraph_runtime/test_graph_builder.py
from __future__ import annotations
import pytest
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
        checkpointer=None,
    )
    node_names = set(graph.nodes.keys())
    assert "raciocinar" in node_names
    assert "executar" in node_names
    assert "pos_execucao" in node_names
