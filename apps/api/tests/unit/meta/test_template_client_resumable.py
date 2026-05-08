from __future__ import annotations

import httpx
import pytest

from shared.adapters.meta.template_client import MetaTemplateClient


@pytest.mark.asyncio
async def test_create_resumable_upload_session_returns_id(monkeypatch):
    client = MetaTemplateClient(api_key="k")

    async def fake_post(self, url, *args, **kwargs):
        assert "/app123/uploads" in url
        assert kwargs["params"]["file_length"] == 1024
        assert kwargs["params"]["file_type"] == "image/jpeg"
        return httpx.Response(200, json={"id": "upload:abc"})

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    session = await client.create_resumable_upload_session(
        app_id="app123", file_size=1024, file_type="image/jpeg"
    )
    assert session == "upload:abc"


@pytest.mark.asyncio
async def test_upload_media_resumable_returns_handle(monkeypatch):
    client = MetaTemplateClient(api_key="k")

    async def fake_post(self, url, *args, **kwargs):
        assert "/upload:abc" in url
        assert kwargs["headers"]["file_offset"] == "0"
        assert kwargs["content"] == b"BYTES"
        return httpx.Response(200, json={"h": "4::aW1n=="})

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    handle = await client.upload_media_resumable(session_id="upload:abc", data=b"BYTES")
    assert handle == "4::aW1n=="


@pytest.mark.asyncio
async def test_delete_template_calls_delete(monkeypatch):
    client = MetaTemplateClient(api_key="k")
    captured: dict = {}

    async def fake_delete(self, url, *args, **kwargs):
        captured["url"] = url
        captured["params"] = kwargs.get("params")
        return httpx.Response(200, json={"success": True})

    monkeypatch.setattr(httpx.AsyncClient, "delete", fake_delete)
    await client.delete_template(waba_id="waba1", name="my_tpl")
    assert "waba1/message_templates" in captured["url"]
    assert captured["params"]["name"] == "my_tpl"
