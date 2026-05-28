"""Testes do MetaTemplateClient.edit_template (POST /{template_id}).

A Meta usa POST /{template_id} para editar templates não-aprovados. Aprovados
devem ser bloqueados antes de chegar aqui (responsabilidade do use case).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shared.adapters.meta.template_client import (
    MetaTemplateApiError,
    MetaTemplateClient,
)


@pytest.mark.asyncio
async def test_edit_template_calls_graph_post() -> None:
    client = MetaTemplateClient(api_key="fake-key")
    components = [{"type": "BODY", "text": "Hello {{1}}"}]

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"success": True}
    mock_resp.headers = {}

    mock_http = AsyncMock()
    mock_http.post = AsyncMock(return_value=mock_resp)

    with patch("shared.adapters.meta.template_client.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__.return_value = mock_http
        await client.edit_template(
            template_id="123456789",
            components=components,
            category="MARKETING",
        )

    call = mock_http.post.call_args
    assert call.args[0].endswith("/123456789"), (
        f"URL deve terminar com /123456789, got {call.args[0]}"
    )
    body = call.kwargs["json"]
    assert body["components"] == components
    assert body["category"] == "MARKETING"


@pytest.mark.asyncio
async def test_edit_template_only_components() -> None:
    client = MetaTemplateClient(api_key="fake-key")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"success": True}
    mock_resp.headers = {}

    mock_http = AsyncMock()
    mock_http.post = AsyncMock(return_value=mock_resp)

    with patch("shared.adapters.meta.template_client.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__.return_value = mock_http
        await client.edit_template(template_id="abc", components=[{"type": "BODY", "text": "x"}])

    body = mock_http.post.call_args.kwargs["json"]
    assert "components" in body
    assert "category" not in body  # não envia campo opcional ausente


@pytest.mark.asyncio
async def test_edit_template_raises_meta_api_error_on_error_status() -> None:
    """Status não-OK da Meta deve virar MetaTemplateApiError (não 500 ASGI cru)."""
    client = MetaTemplateClient(api_key="fake-key")

    mock_resp = MagicMock()
    mock_resp.status_code = 400
    mock_resp.headers = {"content-type": "application/json"}
    mock_resp.json.return_value = {
        "error": {
            "message": "Invalid parameter",
            "code": 100,
            "error_subcode": 2388003,
            "error_user_msg": "Os modelos de mensagem só podem ser editados se tiverem sido rejeitados.",
        }
    }

    mock_http = AsyncMock()
    mock_http.post = AsyncMock(return_value=mock_resp)

    with patch("shared.adapters.meta.template_client.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__.return_value = mock_http

        with pytest.raises(MetaTemplateApiError) as exc_info:
            await client.edit_template(template_id="123", components=[])

    assert exc_info.value.status_code == 400
    assert exc_info.value.subcode == 2388003
    assert "rejeitados" in exc_info.value.user_msg
