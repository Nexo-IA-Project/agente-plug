from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from shared.config.settings import get_settings
from shared.domain.value_objects.escalation_reason import EscalationReason

if TYPE_CHECKING:
    from shared.domain.entities.account_config import AccountConfig


class ChatNexoError(RuntimeError):
    pass


_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.2, max=2),
    retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TransportError)),
    reraise=True,
)

_API_PREFIX = "/api/v1"


@dataclass
class ChatNexoClient:
    http: httpx.AsyncClient

    @classmethod
    def from_settings(cls) -> ChatNexoClient:
        s = get_settings()
        client = httpx.AsyncClient(
            base_url=s.chatnexo_base_url,
            headers={"api_access_token": s.chatnexo_api_key},
            timeout=httpx.Timeout(10.0, connect=3.0),
        )
        return cls(http=client)

    @classmethod
    def from_account_config(cls, config: AccountConfig) -> ChatNexoClient:
        client = httpx.AsyncClient(
            base_url=config.integration.chatnexo_base_url,
            headers={"api_access_token": config.integration.chatnexo_api_key},
            timeout=httpx.Timeout(10.0, connect=3.0),
        )
        return cls(http=client)

    @_retry
    async def _post(self, path: str, json: dict[str, Any]) -> httpx.Response:
        response = await self.http.post(f"{_API_PREFIX}{path}", json=json)
        response.raise_for_status()
        return response

    async def _get(self, path: str, **kwargs: Any) -> httpx.Response:
        response = await self.http.get(f"{_API_PREFIX}{path}", **kwargs)
        response.raise_for_status()
        return response

    async def send_message(self, *, account_id: int, conversation_id: int, text: str) -> None:
        await self._post(
            f"/accounts/{account_id}/conversations/{conversation_id}/messages",
            json={"type": "text", "content": text},
        )

    async def send_template(
        self,
        *,
        account_id: int,
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
        self, *, account_id: int, conversation_id: int, reason: EscalationReason
    ) -> None:
        await self._post(
            f"/accounts/{account_id}/conversations/{conversation_id}/transfer",
            json={"reason": reason.value},
        )

    async def add_tag(self, *, account_id: int, conversation_id: int, tag: str) -> None:
        await self._post(
            f"/accounts/{account_id}/conversations/{conversation_id}/tags",
            json={"tag": tag},
        )

    async def get_open_conversation(self, account_id: int, contact_phone: str) -> str | None:
        """Return the open conversation ID for a contact, or None if not found."""
        response = await self._get(
            f"/accounts/{account_id}/conversations",
            params={"contact_phone": contact_phone, "status": "open"},
        )
        data = response.json()
        items = data.get("data", []) if isinstance(data, dict) else data
        return str(items[0]["id"]) if items else None

    async def create_conversation(self, account_id: int, contact_phone: str) -> str:
        """Create a new conversation for a contact and return its ID."""
        response = await self._post(
            f"/accounts/{account_id}/conversations",
            json={"contact_phone": contact_phone},
        )
        data = response.json()
        return str(data["id"])

    async def aclose(self) -> None:
        await self.http.aclose()
