from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

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

    @classmethod
    def with_key(cls, base_url: str, api_key: str) -> ChatNexoClient:
        client = httpx.AsyncClient(
            base_url=base_url,
            headers={"api_access_token": api_key},
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

    async def send_message(self, *, account_id: str, conversation_id: str, text: str) -> None:
        from shared.adapters.chatnexo.message_splitter import split_message

        s = get_settings()
        parts = split_message(
            text,
            max_chars=s.chatnexo_split_max_chars,
            min_chars=s.chatnexo_split_min_chars,
        )

        for i, part in enumerate(parts):
            await self._post(
                f"/accounts/{account_id}/conversations/{conversation_id}/messages",
                json={"type": "text", "content": part},
            )
            if i < len(parts) - 1:
                delay_ms = len(part) * s.chatnexo_delay_ms_per_char
                delay_ms = max(s.chatnexo_min_delay_ms, min(delay_ms, s.chatnexo_max_delay_ms))
                await asyncio.sleep(delay_ms / 1000)

    async def send_template(
        self,
        *,
        account_id: str,
        conversation_id: str,
        template_name: str,
        language: str | None = None,
        variables: dict[str, Any] | None = None,
        header_link: str | None = None,
        header_kind: Literal["image", "video", "document"] | None = None,
        rendered_body: str | None = None,
    ) -> None:
        """Envia template via ChatNexo.

        Estratégia: o ChatNexo (fork Chatwoot) só envia template real para a Meta
        FORA da janela de 24h. Dentro da janela, ele envia o `content` como texto
        livre. Por isso passamos o body renderizado localmente como `content` e
        anexamos `template_params` como metadata (usado para reenvio fora da
        janela quando o ChatNexo dispara via Meta).
        """
        body: dict[str, Any] = {}
        if rendered_body:
            body["content"] = rendered_body
        body["template_params"] = {
            "name": template_name,
            "language": language,
            "processed_params": variables or {},
        }
        if header_link and header_kind:
            body["template_params"]["header"] = {"type": header_kind, "link": header_link}
        await self._post(
            f"/accounts/{account_id}/conversations/{conversation_id}/messages",
            json=body,
        )

    async def transfer_to_human(
        self, *, account_id: str, conversation_id: str, reason: EscalationReason
    ) -> None:
        await self._post(
            f"/accounts/{account_id}/conversations/{conversation_id}/transfer",
            json={"reason": reason.value},
        )

    async def add_tag(self, *, account_id: str, conversation_id: str, tag: str) -> None:
        await self._post(
            f"/accounts/{account_id}/conversations/{conversation_id}/tags",
            json={"tag": tag},
        )

    async def get_open_conversation(self, account_id: str, contact_phone: str) -> str | None:
        """Return the open conversation ID for a contact, or None if not found.

        ChatNexo retorna 404 quando não há conversa aberta para o contato — esse é
        o caso normal de primeira compra, não erro. Tratamos como None.

        ChatNexo response shapes possíveis:
        - `{"data": {"meta": ..., "payload": [...]}}` (Chatwoot v3 contact_conversations)
        - `{"data": [...]}`
        - `[...]`
        """
        import logging

        log = logging.getLogger(__name__)

        try:
            response = await self._get(
                f"/accounts/{account_id}/conversations",
                params={"contact_phone": contact_phone, "status": "open"},
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return None
            raise

        data = response.json()
        log.warning(
            "chatnexo_get_open_conversation_response",
            extra={"shape": str(type(data).__name__), "preview": str(data)[:300]},
        )

        # Normalize: extract list of conversations from variable response shape
        if isinstance(data, dict):
            inner = data.get("data", data)
            if isinstance(inner, dict):
                items = inner.get("payload", inner.get("conversations", []))
            else:
                items = inner
        else:
            items = data

        if not isinstance(items, list) or not items:
            return None

        first = items[0]
        if not isinstance(first, dict):
            return None

        conv_id = first.get("id") or first.get("conversation_id")
        return str(conv_id) if conv_id is not None else None

    async def create_conversation(self, account_id: str, contact_phone: str) -> str:
        """Create a new conversation for a contact and return its ID."""
        s = get_settings()
        # str() para garantir serialização caso receba value object Phone
        response = await self._post(
            f"/accounts/{account_id}/conversations",
            json={"contact_phone": str(contact_phone), "inbox_id": s.chatnexo_inbox_id},
        )
        data = response.json()
        return str(data["id"])

    async def aclose(self) -> None:
        await self.http.aclose()
