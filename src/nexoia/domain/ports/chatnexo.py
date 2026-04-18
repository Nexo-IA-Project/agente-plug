from __future__ import annotations

from typing import Any, Protocol, runtime_checkable
from uuid import UUID


@runtime_checkable
class ChatNexoPort(Protocol):
    async def send_message(
        self, *, account_id: UUID, conversation_id: int, text: str
    ) -> None: ...

    async def send_template(
        self,
        *,
        account_id: UUID,
        conversation_id: int,
        template_name: str,
        variables: dict[str, Any],
    ) -> None: ...

    async def transfer_to_human(
        self, *, account_id: UUID, conversation_id: int, reason: str
    ) -> None: ...

    async def add_tag(
        self, *, account_id: UUID, conversation_id: int, tag: str
    ) -> None: ...
