from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class LLMPort(Protocol):
    async def complete_json(
        self,
        *,
        system: str,
        user: str,
        json_schema: dict[str, Any],
        temperature: float = 0.2,
    ) -> dict[str, Any]: ...

    async def complete_text(
        self,
        *,
        system: str,
        user: str,
        temperature: float = 0.7,
    ) -> str: ...

    async def embed(self, *, texts: list[str]) -> list[list[float]]: ...
