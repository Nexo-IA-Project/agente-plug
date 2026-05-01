from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class InMemoryMetaTemplates:
    """In-memory Meta templates registry. Fase 1: manual seed."""

    _templates: dict[str, dict[str, Any]] = field(default_factory=dict)

    def register(
        self, *, name: str, meta_id: str, language: str, variables: list[str]
    ) -> None:
        self._templates[name] = {
            "meta_id": meta_id,
            "language": language,
            "variables": variables,
        }

    async def get_approved_template(self, *, name: str) -> dict[str, Any] | None:
        return self._templates.get(name)
