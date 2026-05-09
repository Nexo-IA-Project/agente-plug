from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Literal
from uuid import UUID, uuid4

from shared.application.use_cases.meta_templates.validators import validate_media_file
from shared.domain.ports.storage import StoragePort

MediaKind = Literal["IMAGE", "VIDEO", "DOCUMENT"]


@dataclass(frozen=True)
class UploadTemplateMediaInput:
    account_id: UUID
    kind: MediaKind
    data: bytes
    mime: str
    original_filename: str


@dataclass(frozen=True)
class UploadTemplateMediaOutput:
    media_url: str
    media_object_key: str
    media_kind: MediaKind
    sha256: str
    size: int


_EXT_BY_MIME = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "video/mp4": "mp4",
    "application/pdf": "pdf",
}


class UploadTemplateMedia:
    def __init__(self, *, storage: StoragePort) -> None:
        self._storage = storage

    async def execute(self, payload: UploadTemplateMediaInput) -> UploadTemplateMediaOutput:
        err = validate_media_file(kind=payload.kind, size=len(payload.data), mime=payload.mime)
        if err:
            raise ValueError(err.code)

        ext = (
            _EXT_BY_MIME.get(payload.mime)
            or PurePosixPath(payload.original_filename).suffix.lstrip(".")
            or "bin"
        )
        key = f"accounts/{payload.account_id}/templates/{uuid4()}.{ext}"

        obj = await self._storage.upload(key=key, data=payload.data, content_type=payload.mime)
        return UploadTemplateMediaOutput(
            media_url=obj.url,
            media_object_key=obj.object_key,
            media_kind=payload.kind,
            sha256=obj.sha256,
            size=obj.size,
        )
