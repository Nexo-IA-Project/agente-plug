# tests/unit/infrastructure/skills/test_knowledge_skills.py
from __future__ import annotations

from unittest.mock import AsyncMock

from nexoia.infrastructure.skills.knowledge import make_knowledge_skills


def test_make_knowledge_skills_returns_two_tools():
    skills = make_knowledge_skills(
        knowledge_repo=AsyncMock(),
        usage_log_repo=AsyncMock(),
        chatnexo=AsyncMock(),
    )
    assert len(skills) == 2


def test_make_knowledge_skills_tool_names():
    skills = make_knowledge_skills(
        knowledge_repo=AsyncMock(),
        usage_log_repo=AsyncMock(),
        chatnexo=AsyncMock(),
    )
    names = {s.name for s in skills}
    assert names == {"buscar_conhecimento", "buscar_conhecimento_com_contexto"}
