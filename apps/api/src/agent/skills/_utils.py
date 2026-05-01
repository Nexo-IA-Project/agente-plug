# apps/api/src/agent/skills/_utils.py
"""Shared helpers used by every skill folder."""
from __future__ import annotations

from pathlib import Path


def _load_instructions(skill_file: str) -> str:
    """Load the instructions.md sitting next to the calling skill.py.

    Usage inside any skill.py:
        from agent.skills._utils import _load_instructions
        description = _load_instructions(__file__)
    """
    instructions_path = Path(skill_file).parent / "instructions.md"
    return instructions_path.read_text(encoding="utf-8").strip()
