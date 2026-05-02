from __future__ import annotations

from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode

from agent.react_node import (
    _roteador,
    make_pos_execucao_node,
    make_raciocinar_node,
)
from agent.skill_loader import Adapters, load_skills
from agent.state import AgentState
from shared.domain.ports.cademi_port import CademiPort
from shared.domain.ports.chatnexo import ChatNexoPort
from shared.domain.ports.hubla_port import HublaPort
from shared.domain.ports.knowledge import KnowledgePort
from shared.domain.ports.legal_history_port import LegalHistoryPort
from shared.domain.ports.refund_mutex import RefundMutexPort


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
    knowledge_repo: KnowledgePort,
    usage_log_repo: Any,
    checkpointer: BaseCheckpointSaver | None = None,
) -> Any:
    adapters = Adapters(
        access_repo=access_repo,
        cademi=cademi,
        chatnexo=chatnexo,
        refund_repo=refund_repo,
        hubla=hubla,
        legal_history=legal_history,
        refund_mutex=refund_mutex,
        knowledge_repo=knowledge_repo,
        usage_log_repo=usage_log_repo,
    )
    skills = load_skills(adapters)

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
