"""Use case: editar template Meta em status não-aprovado.

A Meta API só aceita edição de templates em PENDING ou REJECTED. APPROVED é
imutável (exceto `category` em alguns casos, que o frontend não usa por simplicidade).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID


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


class EditMetaTemplate:
    """Edita um template Meta existente (não-aprovado).

    Pipeline:
      1. Busca o template no banco (por id + account_id).
      2. Se não existir → LookupError.
      3. Se status == APPROVED → MetaTemplateApprovedError.
      4. Chama MetaTemplateClient.edit_template (POST /{meta_template_id}).
      5. Persiste mudanças no banco via repo.update.
      6. Retorna o template atualizado.
    """

    def __init__(self, *, repo: Any, meta_client: Any) -> None:
        self._repo = repo
        self._meta_client = meta_client

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
