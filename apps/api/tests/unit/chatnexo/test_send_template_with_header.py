from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shared.adapters.chatnexo.client import ChatNexoClient


@pytest.mark.asyncio
async def test_send_template_without_header():
    http = MagicMock()
    http.post = AsyncMock()
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    http.post.return_value = mock_response
    client = ChatNexoClient(http=http)

    await client.send_template(
        account_id="a", conversation_id="c",
        template_name="t", language="pt_BR", variables={"1": "Fabio"},
    )

    http.post.assert_called_once()
    body = http.post.call_args.kwargs["json"]
    assert "header" not in body
    assert body["template_name"] == "t"


@pytest.mark.asyncio
async def test_send_template_with_image_header():
    http = MagicMock()
    http.post = AsyncMock()
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    http.post.return_value = mock_response
    client = ChatNexoClient(http=http)

    await client.send_template(
        account_id="a", conversation_id="c",
        template_name="t", language="pt_BR", variables={"1": "x"},
        header_link="https://media.example.com/x.jpg",
        header_kind="image",
    )

    http.post.assert_called_once()
    body = http.post.call_args.kwargs["json"]
    assert body["header"] == {
        "type": "image",
        "link": "https://media.example.com/x.jpg",
    }
