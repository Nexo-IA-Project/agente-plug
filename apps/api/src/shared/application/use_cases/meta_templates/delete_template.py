from __future__ import annotations

from typing import Awaitable, Callable
from uuid import UUID

import structlog

from shared.adapters.db.repositories.meta_template_repo import MetaTemplateRepository
from shared.adapters.meta.template_client import MetaTemplateClient
from shared.domain.ports.storage import StoragePort

log = structlog.get_logger(__name__)


class MetaTemplateInUse(Exception):
    def __init__(self, flows: list[dict]) -> None:
        super().__init__("template em uso por flows")
        self.flows = flows


FlowUsageCheck = Callable[[UUID, str], Awaitable[list[dict]]]


class DeleteTemplate:
    def __init__(
        self,
        *,
        repo: MetaTemplateRepository,
        meta_client: MetaTemplateClient,
        storage: StoragePort | None,
        flow_usage_check: FlowUsageCheck,
    ) -> None:
        self._repo = repo
        self._meta = meta_client
        self._storage = storage
        self._check_usage = flow_usage_check

    async def execute(self, *, account_id: UUID, template_id: UUID, waba_id: str) -> None:
        template = await self._repo.get(template_id, account_id)
        if not template:
            raise LookupError("META_TEMPLATE_NOT_FOUND")

        flows = await self._check_usage(account_id, template.name)
        if flows:
            raise MetaTemplateInUse(flows=flows)

        await self._meta.delete_template(waba_id=waba_id, name=template.name)

        if template.media_object_key and self._storage is not None:
            try:
                await self._storage.delete(key=template.media_object_key)
            except Exception as exc:
                log.warning(
                    "r2_cleanup_pending",
                    template_id=str(template_id),
                    object_key=template.media_object_key,
                    error=str(exc),
                )

        await self._repo.delete(template_id)
        log.info("meta_template_deleted", template_id=str(template_id), name=template.name)
