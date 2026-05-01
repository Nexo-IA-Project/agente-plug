from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog

from shared.domain.ports.chatnexo import ChatNexoPort

log = structlog.get_logger(__name__)

_FALLBACK_TEMPLATE = "fallback_generic"


class MessageDispatcher:
    def __init__(self, chatnexo: ChatNexoPort, conversation_repo: Any) -> None:
        self._chatnexo = chatnexo
        self._conv_repo = conversation_repo

    async def send(self, account_id: str, conversation_id: str, content: str) -> None:
        conv = await self._conv_repo.find_by_chatnexo_id(account_id, conversation_id)
        within_window = bool(
            conv and conv.window_expires_at and conv.window_expires_at > datetime.now(UTC)
        )

        if within_window:
            await self._chatnexo.send_message(
                account_id=account_id,
                conversation_id=conversation_id,
                text=content,
            )
            log.info("message_sent_free_text", account_id=account_id)
        else:
            await self._chatnexo.send_template(
                account_id=account_id,
                conversation_id=conversation_id,
                template_name=_FALLBACK_TEMPLATE,
                variables={},
            )
            log.info("message_sent_template_fallback", account_id=account_id)
