from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class TemplateComponentResponse(BaseModel):
    type: str
    format: str | None = None
    text: str | None = None
    buttons: list[dict[str, Any]] | None = None


class MetaTemplateResponse(BaseModel):
    id: str
    name: str
    category: str
    language: str
    status: str
    components: list[TemplateComponentResponse]
    rejection_reason: str | None = None


class CreateTemplateRequest(BaseModel):
    name: str
    category: str          # MARKETING | UTILITY | AUTHENTICATION
    language: str          # pt_BR | en_US
    components: list[dict[str, Any]]
