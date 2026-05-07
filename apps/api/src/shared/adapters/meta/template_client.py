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
    def from_account_config(cls, config: Any) -> "MetaTemplateClient":
        return cls(api_key=config.integration.meta_api_key)

    @classmethod
    def from_settings(cls, settings: Any) -> "MetaTemplateClient":
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

    async def create_template(
        self, waba_id: str, payload: CreateTemplatePayload
    ) -> MetaTemplate:
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
            content_type = resp.headers.get("content-type", "")
            error_body = resp.json() if content_type.startswith("application/json") else {"message": resp.text}
            log.warning("meta_create_template_error", status=resp.status_code, body=error_body)
            resp.raise_for_status()
        raw = resp.json()
        return MetaTemplate(
            id=raw.get("id", ""),
            name=payload.name,
            category=payload.category,
            language=payload.language,
            status=raw.get("status", "PENDING"),
            components=[_parse_component(c) for c in payload.components],
        )
