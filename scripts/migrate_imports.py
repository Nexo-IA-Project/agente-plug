#!/usr/bin/env python3
"""Rewrite nexoia.* imports to the new package layout.

Usage:
    python scripts/migrate_imports.py
"""
from __future__ import annotations

import sys
from pathlib import Path

REPLACEMENTS: list[tuple[str, str]] = [
    # Most specific first (guards move to agent, not shared.domain)
    ("from nexoia.domain.policies.guards", "from agent.guards"),
    # LangGraph renames
    ("from nexoia.infrastructure.langgraph_runtime.graph_builder", "from agent.graph"),
    ("from nexoia.infrastructure.langgraph_runtime.nodes", "from agent.react_node"),
    ("from nexoia.infrastructure.langgraph_runtime.state", "from agent.state"),
    ("from nexoia.infrastructure.langgraph_runtime.checkpointer", "from agent.checkpointer"),
    ("from nexoia.infrastructure.langgraph_runtime", "from agent"),
    # Skills stay in agent (flat for now)
    ("from nexoia.infrastructure.skills", "from agent.skills"),
    # system_prompt moves to agent.prompt
    ("from nexoia.infrastructure.llm.system_prompt", "from agent.prompt"),
    # Remaining adapters
    ("from nexoia.infrastructure.db", "from shared.adapters.db"),
    ("from nexoia.infrastructure.observability", "from shared.adapters.observability"),
    ("from nexoia.infrastructure.kb", "from shared.adapters.kb"),
    ("from nexoia.infrastructure.redis", "from shared.adapters.redis"),
    ("from nexoia.infrastructure.llm", "from shared.adapters.llm"),
    ("from nexoia.infrastructure.meta", "from shared.adapters.meta"),
    ("from nexoia.infrastructure.loja_express", "from shared.adapters.loja_express"),
    ("from nexoia.infrastructure.cademi", "from shared.adapters.cademi"),
    ("from nexoia.infrastructure.chatnexo", "from shared.adapters.chatnexo"),
    ("from nexoia.infrastructure.hubla", "from shared.adapters.hubla"),
    ("from nexoia.infrastructure.clock", "from shared.adapters.clock"),
    ("from nexoia.infrastructure.crypto", "from shared.adapters.crypto"),
    # Memory before application (more specific)
    ("from nexoia.application.memory", "from shared.memory"),
    # Application (handlers, use_cases, scheduler)
    ("from nexoia.application", "from shared.application"),
    # Domain (remaining after guards handled above)
    ("from nexoia.domain", "from shared.domain"),
    # Config
    ("from nexoia.config", "from shared.config"),
    # Interface
    ("from nexoia.interface", "from interface"),
    # Main module
    ("from nexoia.main", "from main"),
    ("import nexoia", "import main"),  # fallback
    # patch() / monkeypatch string literals — same order rules apply
    ("nexoia.domain.policies.guards", "agent.guards"),
    ("nexoia.infrastructure.langgraph_runtime.nodes", "agent.react_node"),
    ("nexoia.infrastructure.langgraph_runtime.graph_builder", "agent.graph"),
    ("nexoia.infrastructure.langgraph_runtime.state", "agent.state"),
    ("nexoia.infrastructure.langgraph_runtime.checkpointer", "agent.checkpointer"),
    ("nexoia.infrastructure.langgraph_runtime", "agent"),
    ("nexoia.infrastructure.skills", "agent.skills"),
    ("nexoia.infrastructure.llm.system_prompt", "agent.prompt"),
    ("nexoia.infrastructure.db", "shared.adapters.db"),
    ("nexoia.infrastructure.observability", "shared.adapters.observability"),
    ("nexoia.infrastructure.kb", "shared.adapters.kb"),
    ("nexoia.infrastructure.redis", "shared.adapters.redis"),
    ("nexoia.infrastructure.llm", "shared.adapters.llm"),
    ("nexoia.infrastructure.meta", "shared.adapters.meta"),
    ("nexoia.infrastructure.loja_express", "shared.adapters.loja_express"),
    ("nexoia.infrastructure.cademi", "shared.adapters.cademi"),
    ("nexoia.infrastructure.chatnexo", "shared.adapters.chatnexo"),
    ("nexoia.infrastructure.hubla", "shared.adapters.hubla"),
    ("nexoia.infrastructure.clock", "shared.adapters.clock"),
    ("nexoia.infrastructure.crypto", "shared.adapters.crypto"),
    ("nexoia.application.memory", "shared.memory"),
    ("nexoia.application", "shared.application"),
    ("nexoia.domain", "shared.domain"),
    ("nexoia.config", "shared.config"),
    ("nexoia.interface", "interface"),
    ("nexoia.main", "main"),
]

SEARCH_ROOTS = [
    Path("apps/api/src"),
    Path("apps/api/tests"),
    Path("apps/api/migrations"),
]


def migrate_file(path: Path) -> bool:
    original = path.read_text(encoding="utf-8")
    text = original
    for old, new in REPLACEMENTS:
        text = text.replace(old, new)
    if text != original:
        path.write_text(text, encoding="utf-8")
        return True
    return False


def main() -> None:
    updated: list[Path] = []
    for root in SEARCH_ROOTS:
        if not root.exists():
            print(f"WARNING: search root not found, skipping: {root}", file=sys.stderr)
            continue
        for py_file in sorted(root.rglob("*.py")):
            if migrate_file(py_file):
                updated.append(py_file)

    for p in updated:
        print(f"  updated: {p}")
    print(f"\nUpdated {len(updated)} files.")


if __name__ == "__main__":
    main()
