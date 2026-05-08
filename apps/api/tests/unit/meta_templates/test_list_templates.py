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
async def test_list_returns_all_when_no_pending():
    repo = AsyncMock()
    meta = AsyncMock()
    repo.list_by_account.return_value = [
        _make_template(id=uuid4(), name="ok", status="APPROVED"),
    ]
    repo.find_pending.return_value = []

    out = await ListTemplates(repo=repo, meta_client=meta).execute(
        account_id=uuid4(), waba_id="w"
    )

    assert len(out) == 1
    meta.list_templates.assert_not_awaited()


@pytest.mark.asyncio
async def test_list_syncs_pending():
    repo = AsyncMock()
    meta = AsyncMock()
    pending_id = uuid4()
    pending = _make_template(id=pending_id, name="pend", status="PENDING")
    repo.list_by_account.return_value = [pending]
    repo.find_pending.return_value = [pending]

    meta.list_templates.return_value = [
        _make_template(name="pend", status="APPROVED", rejection_reason=None),
    ]

    await ListTemplates(repo=repo, meta_client=meta).execute(
        account_id=uuid4(), waba_id="w"
    )

    meta.list_templates.assert_awaited_once_with("w")
    repo.update_status.assert_awaited_once_with(
        pending_id, status="APPROVED", rejection_reason=None
    )
