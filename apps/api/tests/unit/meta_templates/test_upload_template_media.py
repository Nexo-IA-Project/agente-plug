from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from shared.application.use_cases.meta_templates.upload_template_media import (
    UploadTemplateMedia,
    UploadTemplateMediaInput,
)
from shared.domain.ports.storage import StorageObject


@pytest.mark.asyncio
async def test_upload_returns_metadata():
    storage = AsyncMock()
    storage.upload.return_value = StorageObject(
        url="https://media.example.com/accounts/abc/templates/xxx.jpg",
        object_key="accounts/abc/templates/xxx.jpg",
        size=1024,
        sha256="deadbeef",
        content_type="image/jpeg",
    )

    use_case = UploadTemplateMedia(storage=storage)
    out = await use_case.execute(
        UploadTemplateMediaInput(
            account_id=uuid4(),
            kind="IMAGE",
            data=b"x" * 1024,
            mime="image/jpeg",
            original_filename="photo.jpg",
        )
    )

    storage.upload.assert_awaited_once()
    call = storage.upload.await_args.kwargs
    assert call["key"].startswith("accounts/")
    assert call["key"].endswith(".jpg")
    assert call["content_type"] == "image/jpeg"

    assert out.media_url.startswith("https://media.example.com/")
    assert out.media_kind == "IMAGE"
    assert out.size == 1024


@pytest.mark.asyncio
async def test_upload_rejects_oversize():
    storage = AsyncMock()
    use_case = UploadTemplateMedia(storage=storage)
    with pytest.raises(ValueError, match="MEDIA_SIZE_EXCEEDED"):
        await use_case.execute(
            UploadTemplateMediaInput(
                account_id=uuid4(),
                kind="IMAGE",
                data=b"x" * (10 * 1024 * 1024),
                mime="image/jpeg",
                original_filename="huge.jpg",
            )
        )
    storage.upload.assert_not_awaited()


@pytest.mark.asyncio
async def test_upload_rejects_wrong_mime():
    storage = AsyncMock()
    use_case = UploadTemplateMedia(storage=storage)
    with pytest.raises(ValueError, match="MEDIA_TYPE_INVALID"):
        await use_case.execute(
            UploadTemplateMediaInput(
                account_id=uuid4(),
                kind="IMAGE",
                data=b"x" * 1024,
                mime="image/gif",
                original_filename="anim.gif",
            )
        )
