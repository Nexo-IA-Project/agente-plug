"""Testes do ChatNexoClient.send_template.

Após o refactor de Chatwoot template params (commit 7f80646), o body do POST
mudou de `{type, template_name, variables}` para `{content?, template_params}`
porque ChatNexo armazena os params via metadata e dispara o conteúdo real via
`content` (dentro da janela 24h) ou via Meta (fora da janela).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from shared.adapters.chatnexo.client import ChatNexoClient


@pytest.mark.asyncio
async def test_send_template_without_header_and_without_rendered_body():
    http = MagicMock()
    http.post = AsyncMock()
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    http.post.return_value = mock_response
    client = ChatNexoClient(http=http)

    await client.send_template(
        account_id="a",
        conversation_id="c",
        template_name="t",
        language="pt_BR",
        variables={"1": "Fabio"},
    )

    http.post.assert_called_once()
    body = http.post.call_args.kwargs["json"]
    # Sem rendered_body → não tem content
    assert "content" not in body
    # template_params contém name + language + processed_params
    assert body["template_params"]["name"] == "t"
    assert body["template_params"]["language"] == "pt_BR"
    assert body["template_params"]["processed_params"] == {"1": "Fabio"}
    # Sem header
    assert "header" not in body["template_params"]


@pytest.mark.asyncio
async def test_send_template_with_image_header():
    http = MagicMock()
    http.post = AsyncMock()
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    http.post.return_value = mock_response
    client = ChatNexoClient(http=http)

    await client.send_template(
        account_id="a",
        conversation_id="c",
        template_name="t",
        language="pt_BR",
        variables={"1": "x"},
        header_link="https://media.example.com/x.jpg",
        header_kind="image",
    )

    http.post.assert_called_once()
    body = http.post.call_args.kwargs["json"]
    # Header vai dentro de template_params
    assert body["template_params"]["header"] == {
        "type": "image",
        "link": "https://media.example.com/x.jpg",
    }


@pytest.mark.asyncio
async def test_send_template_with_rendered_body_uses_content_field():
    """Quando rendered_body é fornecido, o ChatNexo envia como content texto livre
    (janela 24h aberta) e mantém template_params como metadata."""
    http = MagicMock()
    http.post = AsyncMock()
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    http.post.return_value = mock_response
    client = ChatNexoClient(http=http)

    await client.send_template(
        account_id="a",
        conversation_id="c",
        template_name="cpm1",
        language="pt_PT",
        variables={"name": "Fabio"},
        rendered_body="Olá Fabio, bem-vindo!",
    )

    body = http.post.call_args.kwargs["json"]
    assert body["content"] == "Olá Fabio, bem-vindo!"
    assert body["template_params"]["name"] == "cpm1"
    assert body["template_params"]["processed_params"] == {"name": "Fabio"}
