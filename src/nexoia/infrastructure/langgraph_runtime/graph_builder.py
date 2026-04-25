from __future__ import annotations

from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode

from nexoia.domain.ports.cademi_port import CademiPort
from nexoia.domain.ports.chatnexo import ChatNexoPort
from nexoia.domain.ports.hubla_port import HublaPort
from nexoia.domain.ports.legal_history_port import LegalHistoryPort
from nexoia.domain.ports.refund_mutex import RefundMutexPort
from nexoia.infrastructure.langgraph_runtime.nodes import (
    _roteador,
    make_pos_execucao_node,
    make_raciocinar_node,
)
from nexoia.infrastructure.langgraph_runtime.state import AgentState
from nexoia.infrastructure.skills.access import make_access_skills
from nexoia.infrastructure.skills.core import make_core_skills
from nexoia.infrastructure.skills.refund import make_refund_skills


def build_graph(
    *,
    access_repo: Any,
    cademi: CademiPort,
    chatnexo: ChatNexoPort,
    guard_service: Any,
    long_term_repo: Any,
    llm: Any,
    capability_repo: Any,
    memory_extractor: Any,
    refund_repo: Any,
    hubla: HublaPort,
    legal_history: LegalHistoryPort,
    refund_mutex: RefundMutexPort,
    checkpointer: BaseCheckpointSaver | None = None,
) -> Any:
    skills = (
        make_access_skills(access_repo, cademi, chatnexo)
        + make_refund_skills(refund_repo, hubla, legal_history, refund_mutex)
        + make_core_skills(chatnexo)
    )

    raciocinar_node = make_raciocinar_node(guard_service, long_term_repo, llm)
    pos_execucao_node = make_pos_execucao_node(capability_repo, memory_extractor)

    graph = StateGraph(AgentState)
    graph.add_node("raciocinar", raciocinar_node)
    graph.add_node("executar", ToolNode(skills))
    graph.add_node("pos_execucao", pos_execucao_node)

    graph.set_entry_point("raciocinar")
    graph.add_conditional_edges("raciocinar", _roteador)
    graph.add_edge("executar", "pos_execucao")
    graph.add_edge("pos_execucao", "raciocinar")

    return graph.compile(checkpointer=checkpointer)


# Deprecated alias — kept for backward compatibility during migration
build_main_graph = build_graph
