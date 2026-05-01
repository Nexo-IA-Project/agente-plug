# apps/api/src/agent/skill_loader.py
"""Dynamic skill loader — discovers all skill folders and wires adapters."""
from __future__ import annotations

import importlib
from dataclasses import dataclass
from pathlib import Path

from langchain_core.tools import BaseTool

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


def load_skills(adapters: Adapters) -> list[BaseTool]:
    """Auto-discover every skill folder under agent/skills/ and instantiate it.

    Folders whose names start with '_' are ignored (e.g. _utils.py is not a
    folder, but the pattern guards future helper packages as well).
    """
    skills_dir = Path(__file__).parent / "skills"
    skills: list[BaseTool] = []
    for folder in sorted(skills_dir.iterdir()):
        if folder.is_dir() and not folder.name.startswith("_"):
            module = importlib.import_module(f"agent.skills.{folder.name}")
            skills.append(module.make_skill(adapters))
    return skills
