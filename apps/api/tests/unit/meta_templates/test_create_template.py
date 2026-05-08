from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from shared.application.use_cases.meta_templates.create_template import (
    CreateTemplate,
    CreateTemplateInput,
)


@pytest.mark.asyncio
async def test_create_template_without_media():
    repo = AsyncMock()
    meta_client = AsyncMock()
    storage = AsyncMock()
    repo.create.return_value = MagicMock(id=uuid4())
    meta_client.create_template.return_value = MagicMock(
        id="meta_id_123", status="PENDING"
    )

    use_case = CreateTemplate(repo=repo, meta_client=meta_client, storage=storage)

    await use_case.execute(CreateTemplateInput(
        account_id=uuid4(),
        waba_id="waba1",
        app_id="app1",
        name="boas_vindas",
        category="UTILITY",
        language="pt_BR",
        components=[
            {"type": "BODY", "text": "Olá {{1}}", "example": {"body_text": [["Fabio"]]}},
        ],
        media_url=None,
        media_object_key=None,
        media_kind=None,
    ))

    meta_client.create_resumable_upload_session.assert_not_awaited()
    storage.delete.assert_not_awaited()
    repo.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_template_with_media_does_resumable_upload():
    repo = AsyncMock()
    meta_client = AsyncMock()
    storage = AsyncMock()
    meta_client.create_resumable_upload_session.return_value = "upload:abc"
    meta_client.upload_media_resumable.return_value = "4::HANDLE=="
    meta_client.create_template.return_value = MagicMock(id="m_id", status="PENDING")

    fake_resp = MagicMock()
    fake_resp.content = b"FAKEBYTES"
    fake_resp.raise_for_status.return_value = None

    fake_client = AsyncMock()
    fake_client.__aenter__.return_value = fake_client
    fake_client.__aexit__.return_value = None
    fake_client.get.return_value = fake_resp

    with patch("shared.application.use_cases.meta_templates.create_template.httpx.AsyncClient", return_value=fake_client):
        use_case = CreateTemplate(repo=repo, meta_client=meta_client, storage=storage)
        await use_case.execute(CreateTemplateInput(
            account_id=uuid4(),
            waba_id="waba1",
            app_id="app1",
            name="com_imagem",
            category="UTILITY",
            language="pt_BR",
            components=[
                {"type": "HEADER", "format": "IMAGE", "example": {"header_handle": []}},
                {"type": "BODY", "text": "ok", "example": {"body_text": [[]]}},
            ],
            media_url="https://media.example.com/x.jpg",
            media_object_key="accounts/x/templates/x.jpg",
            media_kind="IMAGE",
        ))

    meta_client.create_resumable_upload_session.assert_awaited_once()
    meta_client.upload_media_resumable.assert_awaited_once()
    args = meta_client.create_template.await_args.args
    payload = args[1]
    header = next(c for c in payload.components if c["type"] == "HEADER")
    assert header["example"]["header_handle"] == ["4::HANDLE=="]


@pytest.mark.asyncio
async def test_create_template_validation_failure_blocks_meta_call():
    repo = AsyncMock()
    meta_client = AsyncMock()
    storage = AsyncMock()
    use_case = CreateTemplate(repo=repo, meta_client=meta_client, storage=storage)

    with pytest.raises(ValueError, match="VALIDATION_FAILED"):
        await use_case.execute(CreateTemplateInput(
            account_id=uuid4(), waba_id="w", app_id="a",
            name="BadName!",
            category="UTILITY", language="pt_BR",
            components=[{"type": "BODY", "text": "ok", "example": {"body_text": [[]]}}],
            media_url=None, media_object_key=None, media_kind=None,
        ))
    meta_client.create_template.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_template_meta_failure_cleans_r2():
    repo = AsyncMock()
    meta_client = AsyncMock()
    storage = AsyncMock()
    meta_client.create_resumable_upload_session.side_effect = RuntimeError("meta down")

    fake_resp = MagicMock()
    fake_resp.content = b"BYTES"
    fake_resp.raise_for_status.return_value = None
    fake_client = AsyncMock()
    fake_client.__aenter__.return_value = fake_client
    fake_client.__aexit__.return_value = None
    fake_client.get.return_value = fake_resp

    with patch("shared.application.use_cases.meta_templates.create_template.httpx.AsyncClient", return_value=fake_client):
        use_case = CreateTemplate(repo=repo, meta_client=meta_client, storage=storage)
        with pytest.raises(RuntimeError, match="meta down"):
            await use_case.execute(CreateTemplateInput(
                account_id=uuid4(), waba_id="w", app_id="a",
                name="ok_name",
                category="UTILITY", language="pt_BR",
                components=[
                    {"type": "HEADER", "format": "IMAGE", "example": {"header_handle": []}},
                    {"type": "BODY", "text": "ok", "example": {"body_text": [[]]}},
                ],
                media_url="https://x/x.jpg",
                media_object_key="accounts/x/templates/x.jpg",
                media_kind="IMAGE",
            ))

    storage.delete.assert_awaited_once_with(key="accounts/x/templates/x.jpg")
