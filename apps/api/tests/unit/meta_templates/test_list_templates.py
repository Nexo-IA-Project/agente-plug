from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from shared.application.use_cases.meta_templates.list_templates import ListTemplates


def _make_template(**attrs):
    """Helper: cria MagicMock com atributos string (name é reservado no MagicMock)."""
    m = MagicMock()
    for k, v in attrs.items():
        setattr(m, k, v)
    return m


@pytest.mark.asyncio
async def test_list_does_not_call_meta_when_no_waba_id():
    repo = AsyncMock()
    meta = AsyncMock()
    repo.list_by_account.return_value = [
        _make_template(id=uuid4(), name="ok", status="APPROVED"),
    ]

    out = await ListTemplates(repo=repo, meta_client=meta).execute(
        account_id=uuid4(), waba_id=""
    )

    assert len(out) == 1
    meta.list_templates.assert_not_awaited()


@pytest.mark.asyncio
async def test_list_syncs_pending_status_from_meta():
    repo = AsyncMock()
    meta = AsyncMock()
    pending_id = uuid4()
    pending = _make_template(id=pending_id, name="pend", status="PENDING")
    repo.list_by_account.return_value = [pending]

    meta.list_templates.return_value = [
        _make_template(
            id="meta_id_1",
            name="pend",
            category="UTILITY",
            language="pt_BR",
            status="APPROVED",
            rejection_reason=None,
            components=[],
        ),
    ]

    await ListTemplates(repo=repo, meta_client=meta).execute(
        account_id=uuid4(), waba_id="w"
    )

    meta.list_templates.assert_awaited_once_with("w")
    repo.update_status.assert_awaited_once_with(
        pending_id, status="APPROVED", rejection_reason=None
    )


@pytest.mark.asyncio
async def test_list_imports_meta_templates_not_in_db():
    """Templates que existem na Meta mas não no DB local devem ser importados."""
    repo = AsyncMock()
    meta = AsyncMock()
    # DB local vazio
    repo.list_by_account.return_value = []

    # Meta retorna 1 template
    meta.list_templates.return_value = [
        _make_template(
            id="meta_id_xyz",
            name="welcome",
            category="UTILITY",
            language="pt_BR",
            status="APPROVED",
            rejection_reason=None,
            components=[],
        ),
    ]

    await ListTemplates(repo=repo, meta_client=meta).execute(
        account_id=uuid4(), waba_id="w"
    )

    repo.create.assert_awaited_once()
    kwargs = repo.create.await_args.kwargs
    assert kwargs["name"] == "welcome"
    assert kwargs["meta_template_id"] == "meta_id_xyz"
    assert kwargs["status"] == "APPROVED"
