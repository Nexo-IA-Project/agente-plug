from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from shared.application.use_cases.meta_templates.delete_template import (
    DeleteTemplate,
    MetaTemplateInUseError,
)


def _template(name="t", media_object_key="k"):
    m = MagicMock()
    m.id = uuid4()
    m.name = name
    m.media_object_key = media_object_key
    return m


@pytest.mark.asyncio
async def test_delete_blocked_when_in_use():
    repo = AsyncMock()
    meta = AsyncMock()
    storage = AsyncMock()
    flow_check = AsyncMock(return_value=[{"id": "f1", "name": "Welcome", "step_position": 2}])
    template = _template()
    repo.get.return_value = template

    use_case = DeleteTemplate(
        repo=repo, meta_client=meta, storage=storage, flow_usage_check=flow_check
    )

    with pytest.raises(MetaTemplateInUseError) as info:
        await use_case.execute(account_id=uuid4(), template_id=template.id, waba_id="w")
    assert info.value.flows[0]["name"] == "Welcome"
    meta.delete_template.assert_not_awaited()
    storage.delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_full_path():
    repo = AsyncMock()
    meta = AsyncMock()
    storage = AsyncMock()
    template = _template()
    repo.get.return_value = template
    flow_check = AsyncMock(return_value=[])

    use_case = DeleteTemplate(
        repo=repo, meta_client=meta, storage=storage, flow_usage_check=flow_check
    )
    await use_case.execute(account_id=uuid4(), template_id=template.id, waba_id="w")

    meta.delete_template.assert_awaited_once_with(waba_id="w", name="t")
    storage.delete.assert_awaited_once_with(key="k")
    repo.delete.assert_awaited_once_with(template.id)


@pytest.mark.asyncio
async def test_delete_without_media_skips_storage():
    repo = AsyncMock()
    meta = AsyncMock()
    storage = AsyncMock()
    template = _template(media_object_key=None)
    repo.get.return_value = template
    flow_check = AsyncMock(return_value=[])

    use_case = DeleteTemplate(
        repo=repo, meta_client=meta, storage=storage, flow_usage_check=flow_check
    )
    await use_case.execute(account_id=uuid4(), template_id=template.id, waba_id="w")

    storage.delete.assert_not_awaited()
    repo.delete.assert_awaited_once()
