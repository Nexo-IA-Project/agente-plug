from __future__ import annotations

from typing import Any
from uuid import UUID

from nexoia.domain.value_objects.escalation_reason import EscalationReason


class FakeChatNexoClient:
    """Fake configurável para testes de ChatNexoPort."""

    def __init__(
        self,
        open_conversation_id: str | None = "conv-default",
        new_conversation_id: str = "conv-created-001",
    ) -> None:
        self._open_conversation_id = open_conversation_id
        self._new_conversation_id = new_conversation_id

        self.last_sent_template: str | None = None
        self.last_sent_variables: dict | None = None
        self.last_sent_text: str | None = None

    async def send_message(
        self, *, account_id: UUID, conversation_id: int, text: str
    ) -> None:
        self.last_sent_text = text

    async def send_template(
        self,
        *,
        account_id: int,
        conversation_id: str,
        template_name: str,
        variables: dict[str, Any],
    ) -> None:
        self.last_sent_template = template_name
        self.last_sent_variables = variables

    async def transfer_to_human(
        self, *, account_id: UUID, conversation_id: int, reason: EscalationReason
    ) -> None:
        pass

    async def add_tag(
        self, *, account_id: UUID, conversation_id: int, tag: str
    ) -> None:
        pass

    async def get_open_conversation(
        self, account_id: int, contact_phone: str
    ) -> str | None:
        return self._open_conversation_id

    async def create_conversation(
        self, account_id: int, contact_phone: str
    ) -> str:
        return self._new_conversation_id
