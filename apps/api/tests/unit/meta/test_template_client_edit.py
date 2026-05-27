"""Testes do MetaTemplateClient.edit_template (POST /{template_id}).

A Meta usa POST /{template_id} para editar templates não-aprovados. Aprovados
devem ser bloqueados antes de chegar aqui (responsabilidade do use case).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from shared.adapters.meta.template_client import MetaTemplateClient


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
async def test_edit_template_raises_on_error_status() -> None:
    client = MetaTemplateClient(api_key="fake-key")

    mock_resp = MagicMock()
    mock_resp.status_code = 400
    mock_resp.headers = {"content-type": "application/json"}
    mock_resp.json.return_value = {"error": {"message": "bad", "code": 132000}}

    def _raise():
        raise httpx.HTTPStatusError("400", request=MagicMock(), response=mock_resp)

    mock_resp.raise_for_status = _raise

    mock_http = AsyncMock()
    mock_http.post = AsyncMock(return_value=mock_resp)

    with patch("shared.adapters.meta.template_client.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__.return_value = mock_http

        with pytest.raises(httpx.HTTPStatusError):
            await client.edit_template(template_id="123", components=[])
