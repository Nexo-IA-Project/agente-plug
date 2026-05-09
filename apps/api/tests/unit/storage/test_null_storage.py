from __future__ import annotations

import pytest

from shared.adapters.storage.null_storage import NullStorage


@pytest.mark.asyncio
async def test_delete_is_noop():
    """delete não deve levantar — apenas loga e segue."""
    null = NullStorage()
    await null.delete(key="any/key.jpg")  # não levanta


@pytest.mark.asyncio
async def test_head_returns_none():
    null = NullStorage()
    obj = await null.head(key="any/key.jpg")
    assert obj is None


@pytest.mark.asyncio
async def test_upload_raises():
    """upload requer storage real — NullStorage não suporta."""
    null = NullStorage()
    with pytest.raises(NotImplementedError):
        await null.upload(key="x", data=b"y", content_type="image/jpeg")


@pytest.mark.asyncio
async def test_download_raises():
    null = NullStorage()
    with pytest.raises(NotImplementedError):
        await null.download(key="x")
