"""Adapter HTTP para o Message Buffer / Nexus Hub.

Chama POST /api/dispatch em vez do ChatNexo quando message_buffer_enabled=True.
O Message Buffer recebe a mensagem, cria/acha a conversa por telefone e entrega
ao ChatMega — sem acionar o loop de IA.
"""
from __future__ import annotations

import httpx
import structlog

log = structlog.get_logger(__name__)


class MessageBufferClient:
    """Envia mensagens de onboarding via Message Buffer.

    Args:
        base_url: URL base da instância (ex.: "https://nexushub.exemplo.com").
        api_key: Bearer token da conta no Message Buffer.
        external_account_id: ID da conta no ChatMega (campo externalAccountId).
        external_inbox_id: ID da inbox no ChatMega (campo externalInboxId).
    """

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        external_account_id: int,
        external_inbox_id: int,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._external_account_id = external_account_id
        self._external_inbox_id = external_inbox_id

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    async def send_text(
        self,
        *,
        to_phone: str,
        text: str,
        idempotency_key: str,
        origin: str = "onboarding",
    ) -> None:
        """Envia mensagem de texto simples via /api/dispatch."""
        payload = {
            "externalAccountId": self._external_account_id,
            "externalInboxId": self._external_inbox_id,
            "toPhone": to_phone,
            "idempotencyKey": idempotency_key,
            "origin": origin,
            "type": "text",
            "content": text,
        }
        await self._post(payload)

    async def send_template(
        self,
        *,
        to_phone: str,
        idempotency_key: str,
        origin: str = "onboarding",
        content: str | None,
        template_name: str | None,
        language: str | None,
        parameter_format: str,
        processed_params: dict[str, str],
        header_link: str | None = None,
        header_kind: str | None = None,
    ) -> None:
        """Envia template WhatsApp via /api/dispatch."""
        template_params: dict = {
            "name": template_name,
            "language": language or "pt_BR",
            "parameter_format": parameter_format,
            "processed_params": processed_params,
        }
        if header_link and header_kind:
            template_params["header"] = {"type": header_kind, "link": header_link}

        payload = {
            "externalAccountId": self._external_account_id,
            "externalInboxId": self._external_inbox_id,
            "toPhone": to_phone,
            "idempotencyKey": idempotency_key,
            "origin": origin,
            "content": content or "",
            "template_params": template_params,
        }
        await self._post(payload)

    async def _post(self, payload: dict) -> None:
        url = f"{self._base_url}/api/dispatch"
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, headers=self._headers(), json=payload)
        if resp.status_code not in (200, 202):
            log.warning(
                "message_buffer_dispatch_error",
                status=resp.status_code,
                body=resp.text[:200],
            )
        resp.raise_for_status()
