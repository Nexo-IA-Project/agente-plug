# tests/unit/infrastructure/test_graph_builder_knowledge.py
from __future__ import annotations

import inspect

from agent.graph import build_graph


def test_build_graph_accepts_knowledge_params():
    """build_graph deve aceitar knowledge_repo e usage_log_repo como parâmetros."""
    sig = inspect.signature(build_graph)
    assert "knowledge_repo" in sig.parameters, "build_graph deve ter parâmetro knowledge_repo"
    assert "usage_log_repo" in sig.parameters, "build_graph deve ter parâmetro usage_log_repo"
