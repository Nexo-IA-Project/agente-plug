from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class MetaTemplateComponent:
    type: str          # HEADER | BODY | FOOTER | BUTTONS
    format: str | None = None
    text: str | None = None
    buttons: list[dict[str, Any]] | None = None
    example: dict[str, Any] | None = None


@dataclass
class MetaTemplate:
    id: str
    name: str
    category: str       # MARKETING | UTILITY | AUTHENTICATION
    language: str       # pt_BR | en_US
    status: str         # APPROVED | PENDING | REJECTED
    components: list[MetaTemplateComponent]
    rejection_reason: str | None = None


@dataclass
class CreateTemplatePayload:
    name: str
    category: str
    language: str
    components: list[dict[str, Any]]


class MetaTemplatePort(Protocol):
    async def list_templates(self, waba_id: str) -> list[MetaTemplate]: ...
    async def create_template(
        self, waba_id: str, payload: CreateTemplatePayload
    ) -> MetaTemplate: ...
