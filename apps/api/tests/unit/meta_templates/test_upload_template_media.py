"""Testes do UploadTemplateMedia use case (Postgres + dedup)."""
from __future__ import annotations

import hashlib
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from shared.application.use_cases.meta_templates.upload_template_media import (
    MediaTooLargeError,
    UploadTemplateMedia,
    UploadTemplateMediaInput,
)


def _make_record(*, kind: str = "IMAGE", size: int = 100, sha: str = "abc"):
    rec = MagicMock()
    rec.id = uuid4()
    rec.kind = kind
    rec.size_bytes = size
    rec.sha256 = sha
    return rec


@pytest.mark.asyncio
async def test_inserts_new_record_when_sha_not_exists() -> None:
    repo = MagicMock()
    repo.get_by_sha = AsyncMock(return_value=None)
    inserted = _make_record(sha=hashlib.sha256(b"hello").hexdigest())
    repo.insert = AsyncMock(return_value=inserted)

    use_case = UploadTemplateMedia(repo=repo, public_base_url="https://example.com/")
    output = await use_case.execute(
        UploadTemplateMediaInput(
            account_id=uuid4(),
            kind="IMAGE",
            data=b"hello",
            mime="image/png",
            original_filename="x.png",
        )
    )

    repo.insert.assert_called_once()
    assert output.media_url.startswith("https://example.com/public/media/")
    assert output.media_url.endswith(str(inserted.id))
    assert output.media_object_key == str(inserted.id)
    assert output.media_kind == "IMAGE"
    assert output.sha256 == hashlib.sha256(b"hello").hexdigest()


@pytest.mark.asyncio
async def test_reuses_existing_record_on_dedup() -> None:
    existing = _make_record()
    repo = MagicMock()
    repo.get_by_sha = AsyncMock(return_value=existing)
    repo.insert = AsyncMock()

    use_case = UploadTemplateMedia(repo=repo, public_base_url="https://example.com")
    output = await use_case.execute(
        UploadTemplateMediaInput(
            account_id=uuid4(),
            kind="IMAGE",
            data=b"x" * 50,
            mime="image/png",
            original_filename="x.png",
        )
    )

    repo.insert.assert_not_called()
    assert str(existing.id) in output.media_url


@pytest.mark.asyncio
async def test_rejects_image_over_5mb() -> None:
    repo = MagicMock()
    repo.get_by_sha = AsyncMock(return_value=None)
    use_case = UploadTemplateMedia(repo=repo, public_base_url="https://x.com")
    big_data = b"\x00" * (5 * 1024 * 1024 + 1)

    with pytest.raises(MediaTooLargeError) as exc_info:
        await use_case.execute(
            UploadTemplateMediaInput(
                account_id=uuid4(),
                kind="IMAGE",
                data=big_data,
                mime="image/png",
                original_filename="big.png",
            )
        )
    assert exc_info.value.kind == "IMAGE"
    assert exc_info.value.limit == 5 * 1024 * 1024


@pytest.mark.asyncio
async def test_accepts_video_up_to_16mb() -> None:
    repo = MagicMock()
    repo.get_by_sha = AsyncMock(return_value=None)
    repo.insert = AsyncMock(return_value=_make_record(kind="VIDEO", size=16 * 1024 * 1024))
    use_case = UploadTemplateMedia(repo=repo, public_base_url="https://x.com")

    out = await use_case.execute(
        UploadTemplateMediaInput(
            account_id=uuid4(),
            kind="VIDEO",
            data=b"\x00" * (16 * 1024 * 1024),
            mime="video/mp4",
            original_filename="v.mp4",
        )
    )
    assert out.media_kind == "VIDEO"
