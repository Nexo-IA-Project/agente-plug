"""NullStorage: implementa StoragePort sem persistir nada.

Usado quando o caller não tem dependência real de storage (ex.: criar template
sem mídia, deletar template sem mídia em ambiente sem R2 configurado). Permite
manter `storage: StoragePort` como dependência sempre presente nos use cases,
sem `Optional`/`is not None` espalhados pelo código (princípio Null Object).
"""

from __future__ import annotations

import structlog

from shared.domain.ports.storage import StorageObject, StoragePort

log = structlog.get_logger(__name__)


class NullStorage(StoragePort):
    async def upload(
        self, *, key: str, data: bytes, content_type: str
    ) -> StorageObject:
        raise NotImplementedError(
            "NullStorage.upload chamado — operação requer storage configurado (R2)."
        )

    async def download(self, *, key: str) -> bytes:
        raise NotImplementedError(
            "NullStorage.download chamado — operação requer storage configurado (R2)."
        )

    async def delete(self, *, key: str) -> None:
        # Idempotente: sem storage, não há objeto para remover.
        log.info("null_storage_delete_noop", key=key)

    async def head(self, *, key: str) -> StorageObject | None:
        return None
