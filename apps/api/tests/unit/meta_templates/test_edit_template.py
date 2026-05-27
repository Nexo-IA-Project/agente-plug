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
    template.name = "t1"
    template.status = status
    template.meta_template_id = "meta-abc-123"
    template.components = [{"type": "BODY", "text": "old"}]
    template.category = "MARKETING"
    template.media_url = None
    template.media_kind = None
    return template


@pytest.mark.asyncio
async def test_edit_rejects_approved() -> None:
    template = _make_template(status="APPROVED")
    repo = MagicMock()
    repo.get = AsyncMock(return_value=template)
    meta_client = MagicMock()
    meta_client.edit_template = AsyncMock()
    use_case = EditMetaTemplate(repo=repo, meta_client=meta_client)

    with pytest.raises(MetaTemplateApprovedError):
        await use_case.execute(
            EditMetaTemplateInput(
                template_id=template.id,
                account_id=uuid4(),
                components=[{"type": "BODY", "text": "new"}],
            )
        )

    meta_client.edit_template.assert_not_called()


@pytest.mark.asyncio
async def test_edit_calls_meta_and_persists_for_pending() -> None:
    template = _make_template(status="PENDING")
    new_components = [{"type": "BODY", "text": "novo"}]
    account_id = uuid4()
    updated = _make_template(status="PENDING")
    updated.components = new_components
    updated.category = "UTILITY"

    repo = MagicMock()
    repo.get = AsyncMock(side_effect=[template, updated])
    repo.update = AsyncMock()
    meta_client = MagicMock()
    meta_client.edit_template = AsyncMock()
    use_case = EditMetaTemplate(repo=repo, meta_client=meta_client)

    result = await use_case.execute(
        EditMetaTemplateInput(
            template_id=template.id,
            account_id=account_id,
            components=new_components,
            category="UTILITY",
        )
    )

    meta_client.edit_template.assert_called_once()
    call_kwargs = meta_client.edit_template.call_args.kwargs
    assert call_kwargs["template_id"] == "meta-abc-123"
    assert call_kwargs["components"] == new_components
    assert call_kwargs["category"] == "UTILITY"

    repo.update.assert_called_once()
    update_kwargs = repo.update.call_args.kwargs
    assert update_kwargs["template_id"] == template.id
    assert update_kwargs["components"] == new_components
    assert update_kwargs["category"] == "UTILITY"

    assert result is updated


@pytest.mark.asyncio
async def test_edit_raises_lookup_error_when_missing() -> None:
    repo = MagicMock()
    repo.get = AsyncMock(return_value=None)
    meta_client = MagicMock()
    use_case = EditMetaTemplate(repo=repo, meta_client=meta_client)

    with pytest.raises(LookupError):
        await use_case.execute(
            EditMetaTemplateInput(
                template_id=uuid4(),
                account_id=uuid4(),
                components=[],
            )
        )


@pytest.mark.asyncio
async def test_edit_rejected_template_is_allowed() -> None:
    template = _make_template(status="REJECTED")
    new_components = [{"type": "BODY", "text": "fix"}]
    updated = _make_template(status="REJECTED")

    repo = MagicMock()
    repo.get = AsyncMock(side_effect=[template, updated])
    repo.update = AsyncMock()
    meta_client = MagicMock()
    meta_client.edit_template = AsyncMock()
    use_case = EditMetaTemplate(repo=repo, meta_client=meta_client)

    await use_case.execute(
        EditMetaTemplateInput(
            template_id=template.id,
            account_id=uuid4(),
            components=new_components,
        )
    )

    meta_client.edit_template.assert_called_once()
