from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any
from uuid import UUID

import structlog

from shared.adapters.db.repositories.meta_template_repo import MetaTemplateRepository
from shared.adapters.meta.template_client import MetaTemplateClient

log = structlog.get_logger(__name__)


def _components_to_jsonb(components: list[Any]) -> list[dict[str, Any]]:
    """Converte componentes (dataclass ou dict) em formato JSONB."""
    out: list[dict[str, Any]] = []
    for c in components:
        if is_dataclass(c):
            d = {k: v for k, v in asdict(c).items() if v is not None}
            out.append(d)
        elif isinstance(c, dict):
            out.append(c)
    return out


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
        # Sempre tenta sincronizar com Meta API (lista completa).
        if waba_id:
            try:
                meta_list = await self._meta.list_templates(waba_id)
            except Exception as exc:
                log.warning("meta_template_sync_failed", error=str(exc))
            else:
                local_by_name = {
                    r.name: r for r in await self._repo.list_by_account(account_id)
                }
                for meta_t in meta_list:
                    local = local_by_name.get(meta_t.name)
                    if local is None:
                        # Template existe na Meta mas não no nosso DB → cria registro
                        try:
                            await self._repo.create(
                                account_id=account_id,
                                name=meta_t.name,
                                meta_template_id=meta_t.id,
                                category=meta_t.category or "UTILITY",
                                language=meta_t.language,
                                components=_components_to_jsonb(meta_t.components),
                                variables_schema={},
                                status=meta_t.status or "APPROVED",
                                rejection_reason=meta_t.rejection_reason,
                            )
                        except Exception as exc:
                            log.warning(
                                "meta_template_import_failed",
                                name=meta_t.name,
                                error=str(exc),
                            )
                    elif local.status != (meta_t.status or "APPROVED"):
                        await self._repo.update_status(
                            local.id,
                            status=meta_t.status or "APPROVED",
                            rejection_reason=meta_t.rejection_reason,
                        )

        return await self._repo.list_by_account(account_id)
