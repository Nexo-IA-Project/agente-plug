"""Use case: editar template Meta em status não-aprovado.

Regras da Meta WhatsApp Cloud API:
- APPROVED: imutável (exceto `category` em alguns casos — não suportado aqui).
- REJECTED: aceita edit direto via `POST /{template_id}`.
- PENDING (e qualquer outro): a Meta NÃO permite editar — error 2388003
  "Os modelos de mensagem só podem ser editados se tiverem sido rejeitados".
  Para esses casos, o use case faz **delete + recreate** com o mesmo nome
  (dedup da mídia por sha256 evita re-upload).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from shared.application.use_cases.meta_templates.create_template import (
    CreateTemplate,
    CreateTemplateInput,
)


class MetaTemplateApprovedError(Exception):
    """Template está APPROVED — Meta não permite editar."""

    def __init__(self, template_id: UUID, status: str) -> None:
        super().__init__(f"Template {template_id} está {status} — não editável pela Meta")
        self.template_id = template_id
        self.status = status


@dataclass
class EditMetaTemplateInput:
    template_id: UUID
    account_id: UUID
    components: list[dict[str, Any]] | None = None
    category: str | None = None
    media_url: str | None = None
    media_kind: str | None = None
    # Necessários quando o status do template exige delete+create (PENDING).
    # Quando REJECTED, o edit direto não usa esses campos.
    waba_id: str | None = None
    app_id: str | None = None


class EditMetaTemplate:
    """Edita um template Meta — edit direto se REJECTED, delete+create caso contrário."""

    def __init__(
        self,
        *,
        repo: Any,
        meta_client: Any,
        media_repo: Any,
    ) -> None:
        self._repo = repo
        self._meta_client = meta_client
        self._media_repo = media_repo

    async def execute(self, input_: EditMetaTemplateInput) -> Any:
        template = await self._repo.get(
            template_id=input_.template_id, account_id=input_.account_id
        )
        if template is None:
            raise LookupError(
                f"template {input_.template_id} not found for account {input_.account_id}"
            )

        if template.status == "APPROVED":
            raise MetaTemplateApprovedError(input_.template_id, template.status)

        if template.status == "REJECTED":
            return await self._edit_in_place(template, input_)

        # PENDING, PENDING_DELETION, etc. — Meta não aceita edit direto.
        if not input_.waba_id:
            raise ValueError("waba_id é obrigatório para editar template não-rejeitado")
        return await self._delete_and_recreate(template, input_)

    async def _edit_in_place(self, template: Any, input_: EditMetaTemplateInput) -> Any:
        """Caminho rápido para REJECTED: POST /{template_id} na Meta."""
        await self._meta_client.edit_template(
            template_id=template.meta_template_id,
            components=input_.components,
            category=input_.category,
        )
        await self._repo.update(
            template_id=template.id,
            components=input_.components,
            category=input_.category,
            media_url=input_.media_url,
            media_kind=input_.media_kind,
        )
        return await self._repo.get(template_id=input_.template_id, account_id=input_.account_id)

    async def _delete_and_recreate(self, template: Any, input_: EditMetaTemplateInput) -> Any:
        """PENDING e outros não-rejeitados: deleta na Meta + recria com mesmo nome."""
        assert input_.waba_id is not None

        # 1. Delete na Meta (pode lançar MetaTemplateApiError).
        await self._meta_client.delete_template(waba_id=input_.waba_id, name=template.name)

        # 2. Delete local (libera UNIQUE constraint do nome).
        await self._repo.delete(template.id)

        # 3. Recreate na Meta + local via CreateTemplate use case (reusa
        #    a lógica de resumable upload da mídia quando aplicável).
        create_uc = CreateTemplate(
            repo=self._repo,
            meta_client=self._meta_client,
            media_repo=self._media_repo,
        )
        new_record = await create_uc.execute(
            CreateTemplateInput(
                account_id=template.account_id,
                waba_id=input_.waba_id,
                app_id=input_.app_id or "",
                name=template.name,
                category=input_.category or template.category,
                language=template.language,
                components=input_.components or template.components,
                media_url=input_.media_url or template.media_url,
                media_object_key=template.media_object_key,
                media_kind=(input_.media_kind or template.media_kind),
            )
        )
        return new_record
