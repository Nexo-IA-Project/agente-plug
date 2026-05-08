from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal
from uuid import UUID

import httpx
import structlog

from shared.adapters.db.repositories.meta_template_repo import MetaTemplateRepository
from shared.adapters.meta.template_client import MetaTemplateClient
from shared.application.use_cases.meta_templates.validators import (
    validate_template_payload,
)
from shared.domain.ports.meta_template import CreateTemplatePayload
from shared.domain.ports.storage import StoragePort

log = structlog.get_logger(__name__)


@dataclass(frozen=True)
class CreateTemplateInput:
    account_id: UUID
    waba_id: str
    app_id: str
    name: str
    category: str
    language: str
    components: list[dict[str, Any]]
    media_url: str | None
    media_object_key: str | None
    media_kind: Literal["IMAGE", "VIDEO", "DOCUMENT"] | None


_MIME_BY_KIND = {
    "IMAGE": "image/jpeg",
    "VIDEO": "video/mp4",
    "DOCUMENT": "application/pdf",
}


class CreateTemplate:
    def __init__(
        self,
        *,
        repo: MetaTemplateRepository,
        meta_client: MetaTemplateClient,
        storage: StoragePort,
    ) -> None:
        self._repo = repo
        self._meta = meta_client
        self._storage = storage

    async def execute(self, payload: CreateTemplateInput) -> Any:
        # 1. Validate
        errors = validate_template_payload({
            "name": payload.name,
            "category": payload.category,
            "language": payload.language,
            "components": payload.components,
        })
        if errors:
            raise ValueError(f"VALIDATION_FAILED: {[e.code for e in errors]}")

        components = [dict(c) for c in payload.components]

        # 2. Resumable upload Meta (se houver mídia)
        if payload.media_url and payload.media_object_key and payload.media_kind:
            try:
                async with httpx.AsyncClient(timeout=60) as http:
                    r = await http.get(payload.media_url)
                    r.raise_for_status()
                    media_bytes = r.content

                session_id = await self._meta.create_resumable_upload_session(
                    app_id=payload.app_id,
                    file_size=len(media_bytes),
                    file_type=_MIME_BY_KIND[payload.media_kind],
                )
                handle = await self._meta.upload_media_resumable(
                    session_id=session_id, data=media_bytes
                )
                # Injetar handle no header
                for c in components:
                    if c.get("type") == "HEADER":
                        c.setdefault("example", {})
                        c["example"]["header_handle"] = [handle]
                        break
            except Exception:
                # Limpa R2 pra não deixar órfão
                log.warning("meta_create_failed_cleaning_r2", key=payload.media_object_key)
                try:
                    await self._storage.delete(key=payload.media_object_key)
                except Exception:
                    log.error("r2_cleanup_failed", key=payload.media_object_key)
                raise

        # 3. Criar template na Meta
        try:
            meta_template = await self._meta.create_template(
                payload.waba_id,
                CreateTemplatePayload(
                    name=payload.name,
                    category=payload.category,
                    language=payload.language,
                    components=components,
                ),
            )
        except Exception:
            if payload.media_object_key:
                try:
                    await self._storage.delete(key=payload.media_object_key)
                except Exception:
                    log.error("r2_cleanup_failed", key=payload.media_object_key)
            raise

        # 4. Persistir
        record = await self._repo.create(
            account_id=payload.account_id,
            name=payload.name,
            meta_template_id=meta_template.id,
            category=payload.category,
            language=payload.language,
            components=components,
            variables_schema={},
            media_url=payload.media_url,
            media_object_key=payload.media_object_key,
            media_kind=payload.media_kind,
            status=meta_template.status or "PENDING",
        )
        log.info(
            "meta_template_created",
            template_id=str(record.id),
            meta_template_id=meta_template.id,
            has_media=bool(payload.media_url),
        )
        return record
