"""Use case: upload de mídia de template — agora salva no Postgres (BYTEA) com dedup por sha256."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Literal
from uuid import UUID

# Limites de tamanho por kind (em bytes). Conforme Spec B (mais conservador que a Meta).
_SIZE_LIMITS: dict[str, int] = {
    "IMAGE": 5 * 1024 * 1024,  # 5 MB
    "VIDEO": 16 * 1024 * 1024,  # 16 MB
    "DOCUMENT": 16 * 1024 * 1024,  # 16 MB
}

MediaKind = Literal["IMAGE", "VIDEO", "DOCUMENT"]


class MediaTooLargeError(Exception):
    """Lançado quando o arquivo excede o limite do `kind`."""

    def __init__(self, kind: str, size: int, limit: int) -> None:
        super().__init__(f"{kind} de {size} bytes excede o limite de {limit} bytes")
        self.kind = kind
        self.size = size
        self.limit = limit


@dataclass(frozen=True)
class UploadTemplateMediaInput:
    account_id: UUID
    kind: MediaKind
    data: bytes
    mime: str
    original_filename: str


@dataclass(frozen=True)
class UploadTemplateMediaOutput:
    media_id: UUID
    media_url: str
    media_object_key: str  # = str(media_id) — compat com a interface anterior do schema HTTP
    media_kind: MediaKind
    sha256: str
    size: int


class UploadTemplateMedia:
    """Salva mídia no Postgres (dedup por sha256) e retorna URL pública servida pelo nosso endpoint."""

    def __init__(self, *, repo: Any, public_base_url: str) -> None:
        self._repo = repo
        self._public_base_url = public_base_url.rstrip("/")

    async def execute(self, payload: UploadTemplateMediaInput) -> UploadTemplateMediaOutput:
        limit = _SIZE_LIMITS[payload.kind]
        if len(payload.data) > limit:
            raise MediaTooLargeError(payload.kind, len(payload.data), limit)

        sha256 = hashlib.sha256(payload.data).hexdigest()
        existing = await self._repo.get_by_sha(account_id=payload.account_id, sha256=sha256)
        if existing is not None:
            return self._to_output(existing)

        record = await self._repo.insert(
            account_id=payload.account_id,
            kind=payload.kind,
            mime=payload.mime,
            sha256=sha256,
            size_bytes=len(payload.data),
            data=payload.data,
            original_filename=payload.original_filename,
        )
        return self._to_output(record)

    def _to_output(self, record: Any) -> UploadTemplateMediaOutput:
        return UploadTemplateMediaOutput(
            media_id=record.id,
            media_url=f"{self._public_base_url}/public/media/{record.id}",
            media_object_key=str(record.id),
            media_kind=record.kind,
            sha256=record.sha256,
            size=record.size_bytes,
        )
