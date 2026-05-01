from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class MetaPort(Protocol):
    async def get_approved_template(
        self, *, name: str
    ) -> dict[str, Any] | None: ...
