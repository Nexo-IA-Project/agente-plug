from __future__ import annotations

from typing import Any
from uuid import UUID

import structlog

from shared.adapters.db.repositories.meta_template_repo import MetaTemplateRepository
from shared.adapters.meta.template_client import MetaTemplateClient

log = structlog.get_logger(__name__)


class ListTemplates:
    def __init__(
        self,
        *,
        repo: MetaTemplateRepository,
        meta_client: MetaTemplateClient,
    ) -> None:
        self._repo = repo
        self._meta = meta_client

    async def execute(self, *, account_id: UUID, waba_id: str) -> list[Any]:
        pending = await self._repo.find_pending(account_id)
        if pending and waba_id:
            try:
                meta_list = await self._meta.list_templates(waba_id)
            except Exception as exc:
                log.warning("meta_template_sync_failed", error=str(exc))
            else:
                by_name = {t.name: t for t in meta_list}
                for record in pending:
                    found = by_name.get(record.name)
                    if found and found.status != record.status:
                        await self._repo.update_status(
                            record.id,
                            status=found.status,
                            rejection_reason=found.rejection_reason,
                        )
        return await self._repo.list_by_account(account_id)
