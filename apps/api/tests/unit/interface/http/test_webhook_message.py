from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from interface.http.middleware import CorrelationIdMiddleware
from interface.http.routers import webhook_message


def _make_app(deps):
    app = FastAPI()
    app.add_middleware(CorrelationIdMiddleware)
    webhook_message.configure(
        dedup=deps["dedup"],
        event_repo_factory=lambda: deps["event_repo"],
        queue=deps["queue"],
        expected_api_key="cn-key",
    )
    app.include_router(webhook_message.router)
    return app


def test_message_endpoint_enqueues():
    deps = {
        "dedup": AsyncMock(),
        "event_repo": AsyncMock(),
        "queue": AsyncMock(),
    }
    deps["dedup"].try_mark = AsyncMock(return_value=True)
    deps["event_repo"].insert_if_new = AsyncMock(return_value=object())
    deps["queue"].enqueue = AsyncMock(return_value="j-1")
    client = TestClient(_make_app(deps))

    body = {
        "account_id": 1,
        "conversation_id": 42,
        "contact_id": 7,
        "contact_phone": "11987654321",
        "chatnexo_message_id": "m-1",
        "text": "preciso de ajuda",
        "occurred_at": "2026-04-17T10:00:00Z",
    }
    r = client.post("/webhook/message", json=body, headers={"X-Api-Key": "cn-key"})
    assert r.status_code == 202
    deps["queue"].enqueue.assert_awaited_once()
