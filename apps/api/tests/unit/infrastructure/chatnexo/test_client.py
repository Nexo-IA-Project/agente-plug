import uuid

import httpx

from shared.adapters.chatnexo.client import ChatNexoClient


def _client_with_transport(transport: httpx.MockTransport) -> ChatNexoClient:
    http = httpx.AsyncClient(
        transport=transport,
        base_url="http://chatnexo",
        headers={"X-Api-Key": "k"},
    )
    return ChatNexoClient(http=http)


async def test_send_message_posts_correct_payload() -> None:
    calls: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(req)
        return httpx.Response(200, json={"ok": True})

    client = _client_with_transport(httpx.MockTransport(handler))
    await client.send_message(account_id=uuid.uuid4(), conversation_id=42, text="Olá")
    assert len(calls) == 1
    req = calls[0]
    assert "42" in str(req.url)
    assert req.headers["X-Api-Key"] == "k"


async def test_send_template_posts_template_endpoint() -> None:
    calls: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(req)
        return httpx.Response(200, json={"ok": True})

    client = _client_with_transport(httpx.MockTransport(handler))
    await client.send_template(
        account_id=uuid.uuid4(),
        conversation_id=42,
        template_name="welcome_purchase",
        variables={"name": "Ana"},
    )
    assert len(calls) == 1


async def test_retries_on_5xx_then_succeeds() -> None:
    attempts = {"n": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        if attempts["n"] < 3:
            return httpx.Response(503)
        return httpx.Response(200, json={"ok": True})

    client = _client_with_transport(httpx.MockTransport(handler))
    await client.send_message(account_id=uuid.uuid4(), conversation_id=1, text="ok")
    assert attempts["n"] == 3
