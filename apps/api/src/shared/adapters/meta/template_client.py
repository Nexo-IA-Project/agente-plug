from __future__ import annotations

from typing import Any

import httpx
import structlog

from shared.domain.ports.meta_template import (
    CreateTemplatePayload,
    MetaTemplate,
    MetaTemplateComponent,
)

log = structlog.get_logger(__name__)

_BASE_URL = "https://graph.facebook.com/v19.0"


class MetaTemplateApiError(Exception):
    """Erro estruturado da Graph API ao manipular templates (rejeição da Meta).

    Carrega o `user_msg` amigável que a Meta retorna (em PT-BR quando disponível)
    + subcode para que o router consiga mapear pra HTTP correto sem 500 ASGI cru.
    """

    def __init__(
        self,
        *,
        status_code: int,
        message: str,
        user_msg: str | None = None,
        subcode: int | None = None,
        code: int | None = None,
    ) -> None:
        super().__init__(user_msg or message)
        self.status_code = status_code
        self.message = message
        self.user_msg = user_msg or message
        self.subcode = subcode
        self.code = code


def _raise_meta_error(resp: httpx.Response, *, log_event: str, **log_extras: Any) -> None:
    """Extrai erro estruturado da Meta e lança MetaTemplateApiError.

    Esperado: `resp.status_code` já é não-OK quando chamado.
    """
    content_type = resp.headers.get("content-type", "")
    error_body: dict[str, Any]
    if content_type.startswith("application/json"):
        try:
            error_body = resp.json() or {}
        except ValueError:
            error_body = {"message": resp.text[:200]}
    else:
        error_body = {"message": resp.text[:200]}

    err = error_body.get("error") or {}
    message: str = err.get("message") or error_body.get("message") or "Meta API error"
    user_msg: str | None = err.get("error_user_msg") or err.get("error_user_title")
    subcode = err.get("error_subcode")
    code = err.get("code")

    log.warning(log_event, status=resp.status_code, body=error_body, **log_extras)
    raise MetaTemplateApiError(
        status_code=resp.status_code,
        message=message,
        user_msg=user_msg,
        subcode=subcode,
        code=code,
    )


def _parse_component(raw: dict[str, Any]) -> MetaTemplateComponent:
    return MetaTemplateComponent(
        type=raw.get("type", ""),
        format=raw.get("format"),
        text=raw.get("text"),
        buttons=raw.get("buttons"),
        example=raw.get("example"),
    )


def _parse_template(raw: dict[str, Any]) -> MetaTemplate:
    components = [_parse_component(c) for c in raw.get("components", [])]
    return MetaTemplate(
        id=raw.get("id", ""),
        name=raw.get("name", ""),
        category=raw.get("category", ""),
        language=raw.get("language", ""),
        status=raw.get("status", "PENDING"),
        components=components,
        rejection_reason=raw.get("rejected_reason"),
    )


class MetaTemplateClient:
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    @classmethod
    def from_account_config(cls, config: Any) -> MetaTemplateClient:
        return cls(api_key=config.integration.meta_api_key)

    @classmethod
    def from_settings(cls, settings: Any) -> MetaTemplateClient:
        return cls(api_key=settings.meta_api_key)

    async def list_templates(self, waba_id: str) -> list[MetaTemplate]:
        url = f"{_BASE_URL}/{waba_id}/message_templates"
        params = {"fields": "id,name,category,language,status,components,rejected_reason"}
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                url,
                params=params,
                headers={"Authorization": f"Bearer {self._api_key}"},
                timeout=15,
            )
        if resp.status_code != 200:
            log.warning(
                "meta_list_templates_error",
                status=resp.status_code,
                body=resp.text[:200],
            )
            resp.raise_for_status()
        data = resp.json()
        return [_parse_template(t) for t in data.get("data", [])]

    async def create_template(self, waba_id: str, payload: CreateTemplatePayload) -> MetaTemplate:
        url = f"{_BASE_URL}/{waba_id}/message_templates"
        body = {
            "name": payload.name,
            "category": payload.category,
            "language": payload.language,
            "components": payload.components,
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                json=body,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                timeout=15,
            )
        if resp.status_code not in (200, 201):
            _raise_meta_error(
                resp, log_event="meta_create_template_error", name=payload.name
            )
        raw = resp.json()
        return MetaTemplate(
            id=raw.get("id", ""),
            name=payload.name,
            category=payload.category,
            language=payload.language,
            status=raw.get("status", "PENDING"),
            components=[_parse_component(c) for c in payload.components],
        )

    async def create_resumable_upload_session(
        self, *, app_id: str, file_size: int, file_type: str
    ) -> str:
        url = f"{_BASE_URL}/{app_id}/uploads"
        async with httpx.AsyncClient() as http:
            resp = await http.post(
                url,
                params={"file_length": file_size, "file_type": file_type},
                headers={"Authorization": f"Bearer {self._api_key}"},
                timeout=15,
            )
        if resp.status_code != 200:
            log.warning(
                "meta_create_upload_session_error", status=resp.status_code, body=resp.text[:200]
            )
            resp.raise_for_status()
        data = resp.json()
        session_id = data.get("id", "")
        if not session_id:
            raise RuntimeError(f"Meta upload session sem id: {data}")
        return session_id

    async def upload_media_resumable(self, *, session_id: str, data: bytes) -> str:
        url = f"{_BASE_URL}/{session_id}"
        async with httpx.AsyncClient() as http:
            resp = await http.post(
                url,
                content=data,
                headers={
                    "Authorization": f"OAuth {self._api_key}",
                    "file_offset": "0",
                },
                timeout=60,
            )
        if resp.status_code != 200:
            log.warning("meta_upload_media_error", status=resp.status_code, body=resp.text[:200])
            resp.raise_for_status()
        body = resp.json()
        handle = body.get("h", "")
        if not handle:
            raise RuntimeError(f"Meta upload sem handle: {body}")
        return handle

    async def delete_template(self, *, waba_id: str, name: str) -> None:
        url = f"{_BASE_URL}/{waba_id}/message_templates"
        async with httpx.AsyncClient() as http:
            resp = await http.delete(
                url,
                params={"name": name},
                headers={"Authorization": f"Bearer {self._api_key}"},
                timeout=15,
            )
        if resp.status_code not in (200, 204):
            _raise_meta_error(resp, log_event="meta_delete_template_error", name=name)

    async def edit_template(
        self,
        *,
        template_id: str,
        components: list[dict] | None = None,
        category: str | None = None,
    ) -> None:
        """Edita um template Meta existente (rota Graph: POST /{template_id}).

        A Meta só aceita edição de templates em status PENDING/REJECTED — para
        APPROVED só `category` pode ser alterado. Validação de status fica no
        use case que chama este método.
        """
        url = f"{_BASE_URL}/{template_id}"
        body: dict[str, Any] = {}
        if components is not None:
            body["components"] = components
        if category is not None:
            body["category"] = category
        async with httpx.AsyncClient() as http:
            resp = await http.post(
                url,
                json=body,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                timeout=15,
            )
        if resp.status_code not in (200, 201):
            _raise_meta_error(
                resp, log_event="meta_edit_template_error", template_id=template_id
            )
