from __future__ import annotations

import hashlib
from unittest.mock import MagicMock, patch

import pytest

from shared.adapters.storage.r2 import R2Storage


@pytest.fixture
def r2() -> R2Storage:
    return R2Storage(
        account_id="acc123",
        access_key_id="key",
        secret_access_key="secret",
        bucket_name="my-bucket",
        public_base_url="https://media.example.com",
    )


@pytest.mark.asyncio
async def test_upload_returns_storage_object_with_sha256(r2: R2Storage) -> None:
    data = b"hello world"
    expected_sha = hashlib.sha256(data).hexdigest()

    mock_client = MagicMock()
    with patch.object(r2, "_client", mock_client):
        obj = await r2.upload(
            key="accounts/x/templates/foo.jpg",
            data=data,
            content_type="image/jpeg",
        )

    mock_client.put_object.assert_called_once()
    kwargs = mock_client.put_object.call_args.kwargs
    assert kwargs["Bucket"] == "my-bucket"
    assert kwargs["Key"] == "accounts/x/templates/foo.jpg"
    assert kwargs["Body"] == data
    assert kwargs["ContentType"] == "image/jpeg"
    assert kwargs["Metadata"]["sha256"] == expected_sha

    assert obj.url == "https://media.example.com/accounts/x/templates/foo.jpg"
    assert obj.object_key == "accounts/x/templates/foo.jpg"
    assert obj.size == len(data)
    assert obj.sha256 == expected_sha
    assert obj.content_type == "image/jpeg"


@pytest.mark.asyncio
async def test_delete_calls_boto(r2: R2Storage) -> None:
    mock_client = MagicMock()
    with patch.object(r2, "_client", mock_client):
        await r2.delete(key="accounts/x/templates/foo.jpg")

    mock_client.delete_object.assert_called_once_with(
        Bucket="my-bucket",
        Key="accounts/x/templates/foo.jpg",
    )


@pytest.mark.asyncio
async def test_head_returns_none_when_not_found(r2: R2Storage) -> None:
    from botocore.exceptions import ClientError

    mock_client = MagicMock()
    mock_client.head_object.side_effect = ClientError(
        {"Error": {"Code": "404"}}, "HeadObject"
    )
    with patch.object(r2, "_client", mock_client):
        obj = await r2.head(key="missing.jpg")

    assert obj is None


@pytest.mark.asyncio
async def test_download_returns_bytes(r2: R2Storage) -> None:
    from io import BytesIO

    mock_client = MagicMock()
    mock_client.get_object.return_value = {
        "Body": BytesIO(b"hello world"),
    }
    with patch.object(r2, "_client", mock_client):
        data = await r2.download(key="accounts/x/templates/foo.jpg")

    mock_client.get_object.assert_called_once_with(
        Bucket="my-bucket", Key="accounts/x/templates/foo.jpg"
    )
    assert data == b"hello world"
