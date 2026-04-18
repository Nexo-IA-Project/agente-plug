from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from nexoia.config.settings import get_settings


class ChatNexoError(RuntimeError):
    pass


_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.2, max=2),
    retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TransportError)),
    reraise=True,
)


@dataclass
class ChatNexoClient:
    http: httpx.AsyncClient

    @classmethod
    def from_settings(cls) -> "ChatNexoClient":
        s = get_settings()
        client = httpx.AsyncClient(
            base_url=s.chatnexo_base_url,
            headers={"X-Api-Key": s.chatnexo_api_key},
            timeout=httpx.Timeout(10.0, connect=3.0),
        )
        return cls(http=client)

    @_retry
    async def _post(self, path: str, json: dict[str, Any]) -> httpx.Response:
        response = await self.http.post(path, json=json)
        response.raise_for_status()
        return response

    async def send_message(
        self, *, account_id: UUID, conversation_id: int, text: str
    ) -> None:
        await self._post(
            f"/accounts/{account_id}/conversations/{conversation_id}/messages",
            json={"type": "text", "content": text},
        )

    async def send_template(
        self,
        *,
        account_id: UUID,
        conversation_id: int,
        template_name: str,
        variables: dict[str, Any],
    ) -> None:
        await self._post(
            f"/accounts/{account_id}/conversations/{conversation_id}/messages",
            json={
                "type": "template",
                "template_name": template_name,
                "variables": variables,
            },
        )

    async def transfer_to_human(
        self, *, account_id: UUID, conversation_id: int, reason: str
    ) -> None:
        await self._post(
            f"/accounts/{account_id}/conversations/{conversation_id}/transfer",
            json={"reason": reason},
        )

    async def add_tag(
        self, *, account_id: UUID, conversation_id: int, tag: str
    ) -> None:
        await self._post(
            f"/accounts/{account_id}/conversations/{conversation_id}/tags",
            json={"tag": tag},
        )

    async def aclose(self) -> None:
        await self.http.aclose()
