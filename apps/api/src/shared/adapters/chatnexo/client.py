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
        """Retorna o ID da conversation OPEN do contato com esse phone, ou None.

        IMPORTANTE: o endpoint `/accounts/{id}/conversations` do Chatwoot/ChatNexo
        **ignora** o query param `contact_phone`. Se usado, retorna TODAS as
        conversations da conta — o que faz `items[0]` cair em conversa de OUTRO
        contato e mensagens vazarem (bug crítico encontrado em prod, 2026-05-26).

        Fluxo correto:
          1. `GET /accounts/{id}/contacts/search?q={phone}` → acha contact_id
          2. Filtra pelo phone exato (search é fuzzy match)
          3. `GET /accounts/{id}/contacts/{contact_id}/conversations` → conversas dele
          4. Pega a primeira com `status == "open"`
        """
        import logging

        log = logging.getLogger(__name__)

        # 1. Busca contato por phone
        try:
            search_resp = await self._get(
                f"/accounts/{account_id}/contacts/search",
                params={"q": contact_phone, "include": "contact_inboxes"},
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return None
            raise

        search_data = search_resp.json()
        payload = search_data.get("payload") if isinstance(search_data, dict) else None
        if not isinstance(payload, list):
            payload = (
                search_data.get("data", {}).get("payload", [])
                if isinstance(search_data, dict)
                else []
            )

        # Match exato pelo phone (search é fuzzy — pode retornar similar)
        def _normalize(p: str) -> str:
            return "".join(c for c in p if c.isdigit())

        target = _normalize(contact_phone)
        contact_id = None
        for c in payload if isinstance(payload, list) else []:
            if not isinstance(c, dict):
                continue
            phone = c.get("phone_number") or ""
            if _normalize(str(phone)) == target:
                contact_id = c.get("id")
                break

        if contact_id is None:
            log.info(
                "chatnexo_contact_not_found", extra={"phone_suffix": target[-4:] if target else ""}
            )
            return None

        # 2. Busca conversas desse contato
        try:
            conv_resp = await self._get(
                f"/accounts/{account_id}/contacts/{contact_id}/conversations",
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return None
            raise

        conv_data = conv_resp.json()
        if isinstance(conv_data, dict):
            inner = conv_data.get("data", conv_data)
            if isinstance(inner, dict):
                items = inner.get("payload", inner.get("conversations", []))
            else:
                items = inner
        else:
            items = conv_data

        if not isinstance(items, list):
            return None

        # Pega a primeira conversa OPEN
        for conv in items:
            if not isinstance(conv, dict):
                continue
            if conv.get("status") == "open":
                cid = conv.get("id") or conv.get("conversation_id")
                if cid is not None:
                    return str(cid)

        return None

    async def create_conversation(
        self,
        account_id: str,
        contact_phone: str,
        *,
        inbox_id: int,
        contact_name: str | None = None,
        contact_email: str | None = None,
    ) -> str:
        """Cria contato + contact_inbox + conversation no Chatwoot/ChatNexo.

        Fluxo Chatwoot v3 (validado contra workflow N8N de produção):
          1. POST /contacts {name, email, phone_number, identifier}  ← SEM inbox_id
          2. POST /contacts/{id}/contact_inboxes {inbox_id, source_id=phone-sem-+}
          3. POST /conversations {source_id, inbox_id, contact_id}

        ⚠ POST /contacts com inbox_id no body retorna 404 silenciosamente quando
        a inbox passada no body não bate exatamente com a do account (bug do
        Chatwoot/ChatNexo descoberto em prod 2026-05-26). Sempre criar contact
        sem inbox_id e vincular depois via contact_inboxes.

        `inbox_id` agora vem por parâmetro (do banco via account_config), não
        do env — pra que trocar a inbox pela UI de Settings tenha efeito.
        """
        phone = str(contact_phone)

        # 1. Criar contato — NÃO envia inbox_id (causa 404)
        contact_body: dict[str, Any] = {
            "phone_number": phone,
            "identifier": phone,
        }
        if contact_name:
            contact_body["name"] = contact_name
        if contact_email:
            contact_body["email"] = contact_email

        contact_id: int | None = None
        try:
            contact_resp = await self._post(f"/accounts/{account_id}/contacts", json=contact_body)
            contact_data = contact_resp.json()
            payload = contact_data.get("payload", contact_data)
            contact = payload.get("contact", payload) if isinstance(payload, dict) else {}
            contact_id = contact.get("id") if isinstance(contact, dict) else None
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 422:
                raise
            # 422 = já existe → busca via search
            search_resp = await self._get(
                f"/accounts/{account_id}/contacts/search",
                params={"q": phone, "include": "contact_inboxes"},
            )
            search_payload = search_resp.json().get("payload", [])
            target_digits = "".join(c for c in phone if c.isdigit())
            existing = next(
                (
                    c
                    for c in search_payload
                    if isinstance(c, dict)
                    and "".join(ch for ch in (c.get("phone_number") or "") if ch.isdigit())
                    == target_digits
                ),
                None,
            )
            if existing is None:
                raise
            contact_id = existing.get("id")

        if contact_id is None:
            raise ChatNexoError(f"failed to resolve contact_id for phone={phone[-4:]}")

        # 2. Vincular contato à inbox — source_id = phone sem o "+"
        source_id_input = phone.lstrip("+")
        try:
            ci_resp = await self._post(
                f"/accounts/{account_id}/contacts/{contact_id}/contact_inboxes",
                json={"inbox_id": inbox_id, "source_id": source_id_input},
            )
            source_id = ci_resp.json().get("source_id") or source_id_input
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 422:
                raise
            # 422 = contact_inbox já existe → busca via GET /contacts/{id}
            cl_resp = await self._get(f"/accounts/{account_id}/contacts/{contact_id}")
            cl_payload = cl_resp.json().get("payload", {})
            source_id = next(
                (
                    ci.get("source_id")
                    for ci in cl_payload.get("contact_inboxes", [])
                    if isinstance(ci, dict)
                    and isinstance(ci.get("inbox"), dict)
                    and ci["inbox"].get("id") == inbox_id
                ),
                None,
            )
            if source_id is None:
                raise

        # 3. Criar conversation
        conv_resp = await self._post(
            f"/accounts/{account_id}/conversations",
            json={"source_id": source_id, "inbox_id": inbox_id, "contact_id": contact_id},
        )
        return str(conv_resp.json()["id"])

    async def aclose(self) -> None:
        await self.http.aclose()
