# apps/api/src/agent/skill_loader.py
"""Dynamic skill loader — discovers all skill folders and wires adapters."""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from pathlib import Path

from agent.skill import register_skill
from agent.tool_registry import ToolRegistry
from shared.domain.ports.cademi_port import CademiPort
from shared.domain.ports.chatnexo import ChatNexoPort
from shared.domain.ports.hubla_port import HublaPort
from shared.domain.ports.knowledge import KnowledgePort
from shared.domain.ports.legal_history_port import LegalHistoryPort
from shared.domain.ports.refund_mutex import RefundMutexPort


@dataclass
class Adapters:
    access_repo: object
    cademi: CademiPort
    chatnexo: ChatNexoPort
    refund_repo: object
    hubla: HublaPort
    legal_history: LegalHistoryPort
    refund_mutex: RefundMutexPort
    knowledge_repo: KnowledgePort
    usage_log_repo: object


def build_registry(adapters: Adapters) -> ToolRegistry:
    """Auto-discover every skill folder under agent/skills/ and register each one.

    Folders whose names start with '_' are ignored.
    """
    registry = ToolRegistry()
    skills_dir = Path(__file__).parent / "skills"
    for folder in sorted(skills_dir.iterdir()):
        if folder.is_dir() and not folder.name.startswith("_"):
            module = importlib.import_module(f"agent.skills.{folder.name}")
            skill = module.make_skill(adapters)
            register_skill(registry, skill)
    return registry


