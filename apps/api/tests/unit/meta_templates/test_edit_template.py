"""Testes do use case EditMetaTemplate."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from shared.application.use_cases.meta_templates.edit_template import (
    EditMetaTemplate,
    EditMetaTemplateInput,
    MetaTemplateApprovedError,
)


def _make_template(*, status: str = "PENDING"):
    template = MagicMock()
    template.id = uuid4()
    template.name = "test_template"
    template.status = status
    template.meta_template_id = "meta-abc-123"
    template.components = [{"type": "BODY", "text": "old"}]
    template.category = "MARKETING"
    template.language = "pt_BR"
    template.account_id = uuid4()
    template.media_url = None
    template.media_kind = None
    template.media_object_key = None
    return template


def _make_use_case(repo, meta_client, media_repo=None):
    return EditMetaTemplate(
        repo=repo,
        meta_client=meta_client,
        media_repo=media_repo or MagicMock(),
    )


@pytest.mark.asyncio
async def test_edit_rejects_approved() -> None:
    template = _make_template(status="APPROVED")
    repo = MagicMock()
    repo.get = AsyncMock(return_value=template)
    meta_client = MagicMock()
    meta_client.edit_template = AsyncMock()
    use_case = _make_use_case(repo, meta_client)

    with pytest.raises(MetaTemplateApprovedError):
        await use_case.execute(
            EditMetaTemplateInput(
                template_id=template.id,
                account_id=uuid4(),
                components=[{"type": "BODY", "text": "new"}],
                waba_id="waba-1",
            )
        )

    meta_client.edit_template.assert_not_called()


@pytest.mark.asyncio
async def test_pending_template_does_delete_and_recreate() -> None:
    """Para PENDING, a Meta não aceita edit direto — use case deve delete+create."""
    template = _make_template(status="PENDING")
    new_components = [{"type": "BODY", "text": "novo"}]
    account_id = uuid4()

    repo = MagicMock()
    repo.get = AsyncMock(return_value=template)
    repo.delete = AsyncMock()
    # repo.create é chamado pelo CreateTemplate use case interno
    new_record = MagicMock(id=uuid4(), name=template.name)
    repo.create = AsyncMock(return_value=new_record)

    meta_client = MagicMock()
    meta_client.delete_template = AsyncMock()
    meta_client.create_template = AsyncMock(
        return_value=MagicMock(id="new-meta-id", status="PENDING")
    )
    meta_client.edit_template = AsyncMock()  # NÃO deve ser chamado

    media_repo = MagicMock()

    use_case = _make_use_case(repo, meta_client, media_repo)
    result = await use_case.execute(
        EditMetaTemplateInput(
            template_id=template.id,
            account_id=account_id,
            components=new_components,
            category="UTILITY",
            waba_id="waba-1",
            app_id="app-1",
        )
    )

    # Não tentou edit direto
    meta_client.edit_template.assert_not_called()
    # Deletou na Meta + local
    meta_client.delete_template.assert_called_once_with(
        waba_id="waba-1", name=template.name
    )
    repo.delete.assert_called_once_with(template.id)
    # Recriou (via CreateTemplate use case)
    meta_client.create_template.assert_called_once()
    repo.create.assert_called_once()
    assert result is new_record


@pytest.mark.asyncio
async def test_edit_raises_lookup_error_when_missing() -> None:
    repo = MagicMock()
    repo.get = AsyncMock(return_value=None)
    meta_client = MagicMock()
    use_case = _make_use_case(repo, meta_client)

    with pytest.raises(LookupError):
        await use_case.execute(
            EditMetaTemplateInput(
                template_id=uuid4(),
                account_id=uuid4(),
                components=[],
                waba_id="waba-1",
            )
        )


@pytest.mark.asyncio
async def test_rejected_template_does_edit_in_place() -> None:
    """REJECTED é o único status onde a Meta aceita edit direto (POST /{id})."""
    template = _make_template(status="REJECTED")
    new_components = [{"type": "BODY", "text": "fix"}]
    updated = _make_template(status="REJECTED")

    repo = MagicMock()
    repo.get = AsyncMock(side_effect=[template, updated])
    repo.update = AsyncMock()
    meta_client = MagicMock()
    meta_client.edit_template = AsyncMock()
    meta_client.delete_template = AsyncMock()  # NÃO deve ser chamado

    use_case = _make_use_case(repo, meta_client)
    await use_case.execute(
        EditMetaTemplateInput(
            template_id=template.id,
            account_id=uuid4(),
            components=new_components,
            waba_id="waba-1",
        )
    )

    meta_client.edit_template.assert_called_once()
    meta_client.delete_template.assert_not_called()
    repo.update.assert_called_once()
