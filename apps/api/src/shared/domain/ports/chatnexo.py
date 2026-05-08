from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from shared.domain.value_objects.escalation_reason import EscalationReason


@runtime_checkable
class ChatNexoPort(Protocol):
    async def send_message(self, *, account_id: str, conversation_id: str, text: str) -> None: ...

    async def send_template(
        self,
        *,
        account_id: str,
        conversation_id: str,
        template_name: str,
        variables: dict[str, Any],
    ) -> None: ...

    async def transfer_to_human(
        self, *, account_id: str, conversation_id: str, reason: EscalationReason
    ) -> None: ...

    async def add_tag(self, *, account_id: str, conversation_id: str, tag: str) -> None: ...

    async def get_open_conversation(self, account_id: str, contact_phone: str) -> str | None:
        """Retorna conversation_id se houver conversa aberta, None caso contrário."""
        ...

    async def create_conversation(self, account_id: str, contact_phone: str) -> str:
        """Cria nova conversa e retorna o conversation_id."""
        ...
