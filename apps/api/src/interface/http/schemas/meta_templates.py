from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

MediaKind = Literal["IMAGE", "VIDEO", "DOCUMENT"]
TemplateCategory = Literal["MARKETING", "UTILITY"]
TemplateStatus = Literal["PENDING", "APPROVED", "REJECTED"]


class UploadMediaResponse(BaseModel):
    media_url: str
    media_object_key: str
    media_kind: MediaKind
    sha256: str
    size: int


class CreateTemplateRequest(BaseModel):
    name: str
    category: TemplateCategory
    language: str
    components: list[dict[str, Any]]
    media_url: str | None = None
    media_object_key: str | None = None
    media_kind: MediaKind | None = None


class EditTemplateRequest(BaseModel):
    """Edita campos de um template não-aprovado. Todos opcionais — só atualiza o que vier."""

    components: list[dict[str, Any]] | None = None
    category: TemplateCategory | None = None
    media_url: str | None = None
    media_kind: MediaKind | None = None


class TemplateComponentResponse(BaseModel):
    type: str
    format: str | None = None
    text: str | None = None
    buttons: list[dict[str, Any]] | None = None


class MetaTemplateResponse(BaseModel):
    id: UUID
    name: str
    category: str
    language: str
    status: TemplateStatus
    components: list[dict[str, Any]]
    media_url: str | None = None
    media_kind: MediaKind | None = None
    rejection_reason: str | None = None
    meta_template_id: str | None = None
    created_at: datetime


class DeleteConflictDetail(BaseModel):
    flows: list[dict[str, Any]] = Field(default_factory=list)
