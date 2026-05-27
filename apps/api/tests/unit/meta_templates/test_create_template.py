from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from shared.application.use_cases.meta_templates.create_template import (
    CreateTemplate,
    CreateTemplateInput,
)


def _make_media_repo(data: bytes | None = None) -> MagicMock:
    """Build a media_repo mock. If data is provided, get_by_id retorna row com .data."""
    repo = MagicMock()
    if data is not None:
        media = MagicMock()
        media.data = data
        repo.get_by_id = AsyncMock(return_value=media)
    else:
        repo.get_by_id = AsyncMock(return_value=None)
    return repo


@pytest.mark.asyncio
async def test_create_template_without_media():
    repo = AsyncMock()
    meta_client = AsyncMock()
    media_repo = _make_media_repo()
    repo.create.return_value = MagicMock(id=uuid4())
    meta_client.create_template.return_value = MagicMock(id="meta_id_123", status="PENDING")

    use_case = CreateTemplate(repo=repo, meta_client=meta_client, media_repo=media_repo)

    await use_case.execute(
        CreateTemplateInput(
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
        )
    )

    meta_client.create_resumable_upload_session.assert_not_awaited()
    media_repo.get_by_id.assert_not_awaited()
    repo.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_template_with_media_does_resumable_upload():
    repo = AsyncMock()
    meta_client = AsyncMock()
    media_repo = _make_media_repo(data=b"FAKEBYTES")
    meta_client.create_resumable_upload_session.return_value = "upload:abc"
    meta_client.upload_media_resumable.return_value = "4::HANDLE=="
    meta_client.create_template.return_value = MagicMock(id="m_id", status="PENDING")

    media_id = uuid4()
    use_case = CreateTemplate(repo=repo, meta_client=meta_client, media_repo=media_repo)
    await use_case.execute(
        CreateTemplateInput(
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
            media_object_key=str(media_id),
            media_kind="IMAGE",
        )
    )

    media_repo.get_by_id.assert_awaited_once_with(media_id)
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
    media_repo = _make_media_repo()
    use_case = CreateTemplate(repo=repo, meta_client=meta_client, media_repo=media_repo)

    with pytest.raises(ValueError, match="VALIDATION_FAILED"):
        await use_case.execute(
            CreateTemplateInput(
                account_id=uuid4(),
                waba_id="w",
                app_id="a",
                name="BadName!",
                category="UTILITY",
                language="pt_BR",
                components=[{"type": "BODY", "text": "ok", "example": {"body_text": [[]]}}],
                media_url=None,
                media_object_key=None,
                media_kind=None,
            )
        )
    meta_client.create_template.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_template_invalid_media_object_key_raises():
    repo = AsyncMock()
    meta_client = AsyncMock()
    media_repo = _make_media_repo()

    use_case = CreateTemplate(repo=repo, meta_client=meta_client, media_repo=media_repo)
    with pytest.raises(ValueError, match="MEDIA_OBJECT_KEY_INVALID"):
        await use_case.execute(
            CreateTemplateInput(
                account_id=uuid4(),
                waba_id="w",
                app_id="a",
                name="ok_name",
                category="UTILITY",
                language="pt_BR",
                components=[
                    {"type": "HEADER", "format": "IMAGE", "example": {"header_handle": []}},
                    {"type": "BODY", "text": "ok", "example": {"body_text": [[]]}},
                ],
                media_url="https://x/x.jpg",
                media_object_key="not-a-uuid",
                media_kind="IMAGE",
            )
        )
    meta_client.create_template.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_template_media_not_found_raises():
    repo = AsyncMock()
    meta_client = AsyncMock()
    media_repo = _make_media_repo(data=None)  # get_by_id returns None
    media_id = uuid4()

    use_case = CreateTemplate(repo=repo, meta_client=meta_client, media_repo=media_repo)
    with pytest.raises(ValueError, match="MEDIA_NOT_FOUND"):
        await use_case.execute(
            CreateTemplateInput(
                account_id=uuid4(),
                waba_id="w",
                app_id="a",
                name="ok_name",
                category="UTILITY",
                language="pt_BR",
                components=[
                    {"type": "HEADER", "format": "IMAGE", "example": {"header_handle": []}},
                    {"type": "BODY", "text": "ok", "example": {"body_text": [[]]}},
                ],
                media_url="https://x/x.jpg",
                media_object_key=str(media_id),
                media_kind="IMAGE",
            )
        )
    meta_client.create_template.assert_not_awaited()
