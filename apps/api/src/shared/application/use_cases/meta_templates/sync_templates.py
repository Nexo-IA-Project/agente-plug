"""Full re-sync de templates Meta — substitui o estado do banco pelo da WABA atual.

Diferente do ListTemplates (que só faz upsert de novos), este use case:
- DELETA templates do banco que não existem mais na WABA atual
- Em cascata, DELETA os onboarding_steps que apontam pra templates removidos
- Insere templates novos da WABA
- Atualiza status/components dos existentes

Suporta modo `dry_run`: calcula o diff sem aplicar. Usado pelo frontend
pra mostrar ToastConfirm com o impacto da mudança.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any
from uuid import UUID

import structlog

from shared.adapters.db.repositories.meta_template_repo import MetaTemplateRepository
from shared.adapters.db.repositories.onboarding_flow_repo import OnboardingFlowRepository
from shared.adapters.meta.template_client import MetaTemplateClient

log = structlog.get_logger(__name__)


@dataclass(frozen=True)
class StepImpact:
    flow_id: UUID
    flow_name: str
    step_id: UUID
    position: int
    template_name: str


@dataclass(frozen=True)
class SyncSummary:
    templates_to_delete: list[str] = field(default_factory=list)
    templates_to_insert: list[str] = field(default_factory=list)
    templates_to_update: list[str] = field(default_factory=list)
    steps_to_delete: list[StepImpact] = field(default_factory=list)
    applied: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "templates_to_delete": list(self.templates_to_delete),
            "templates_to_insert": list(self.templates_to_insert),
            "templates_to_update": list(self.templates_to_update),
            "steps_to_delete": [
                {
                    "flow_id": str(s.flow_id),
                    "flow_name": s.flow_name,
                    "step_id": str(s.step_id),
                    "position": s.position,
                    "template_name": s.template_name,
                }
                for s in self.steps_to_delete
            ],
            "applied": self.applied,
        }


def _components_to_jsonb(components: list[Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for c in components:
        if is_dataclass(c):
            d = {k: v for k, v in asdict(c).items() if v is not None}
            out.append(d)
        elif isinstance(c, dict):
            out.append(c)
    return out


class SyncMetaTemplates:
    """Sincroniza templates locais com a WABA atual.

    Use:
        summary = await SyncMetaTemplates(...).execute(
            account_id=..., waba_id=..., dry_run=True
        )
        # summary.steps_to_delete → mostrar no ToastConfirm
        # depois: dry_run=False pra aplicar

    O `dry_run` retorna o diff sem alterar banco/Meta. O modo real aplica
    em transação dentro do session já gerenciado pelo caller.
    """

    def __init__(
        self,
        *,
        repo: MetaTemplateRepository,
        flow_repo: OnboardingFlowRepository,
        meta_client: MetaTemplateClient,
    ) -> None:
        self._repo = repo
        self._flow_repo = flow_repo
        self._meta = meta_client

    async def execute(
        self,
        *,
        account_id: UUID,
        waba_id: str,
        dry_run: bool = False,
    ) -> SyncSummary:
        if not waba_id:
            raise ValueError("waba_id obrigatório pra sincronizar templates")

        # 1. Fonte da verdade — templates atualmente na Meta
        meta_list = await self._meta.list_templates(waba_id)
        meta_by_name = {t.name: t for t in meta_list}
        meta_names = set(meta_by_name.keys())

        # 2. Estado local
        db_list = await self._repo.list_by_account(account_id)
        db_by_name = {t.name: t for t in db_list}
        db_names = set(db_by_name.keys())

        # 3. Diff
        names_to_delete = sorted(db_names - meta_names)
        names_to_insert = sorted(meta_names - db_names)
        names_to_update = sorted(db_names & meta_names)

        # 4. Steps afetados (apontam pra templates a deletar)
        steps_to_delete: list[StepImpact] = []
        for name in names_to_delete:
            pairs = await self._flow_repo.find_steps_by_template_name(
                account_id=account_id, template_name=name
            )
            for step, flow in pairs:
                steps_to_delete.append(
                    StepImpact(
                        flow_id=flow.id,
                        flow_name=flow.name,
                        step_id=step.id,
                        position=step.position,
                        template_name=name,
                    )
                )

        summary = SyncSummary(
            templates_to_delete=names_to_delete,
            templates_to_insert=names_to_insert,
            templates_to_update=names_to_update,
            steps_to_delete=steps_to_delete,
            applied=False,
        )

        if dry_run:
            log.info(
                "meta_templates_sync_preview",
                to_delete=len(names_to_delete),
                to_insert=len(names_to_insert),
                steps_affected=len(steps_to_delete),
            )
            return summary

        # 5. APPLY — ordem: deletar steps → deletar templates → inserir → atualizar
        for impact in steps_to_delete:
            await self._flow_repo.delete_step(impact.step_id)

        for name in names_to_delete:
            template = db_by_name[name]
            await self._repo.delete(template.id)

        for name in names_to_insert:
            meta_t = meta_by_name[name]
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
                log.warning("meta_templates_sync_insert_failed", name=name, error=str(exc))

        for name in names_to_update:
            meta_t = meta_by_name[name]
            local = db_by_name[name]
            new_status = meta_t.status or "APPROVED"
            if local.status != new_status:
                await self._repo.update_status(
                    local.id,
                    status=new_status,
                    rejection_reason=meta_t.rejection_reason,
                )

        log.info(
            "meta_templates_sync_applied",
            deleted=len(names_to_delete),
            inserted=len(names_to_insert),
            updated=len(names_to_update),
            steps_deleted=len(steps_to_delete),
        )

        return SyncSummary(
            templates_to_delete=names_to_delete,
            templates_to_insert=names_to_insert,
            templates_to_update=names_to_update,
            steps_to_delete=steps_to_delete,
            applied=True,
        )
