from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from interface.http.middleware import CorrelationIdMiddleware
from interface.http.routers import webhook_message


@asynccontextmanager
async def _repo_cm(repo):
    yield repo


def _make_app(deps, *, token: str = "nxia_test"):
    app = FastAPI()
    app.add_middleware(CorrelationIdMiddleware)
    webhook_message.configure(
        dedup=deps["dedup"],
        event_repo_factory=lambda: _repo_cm(deps["event_repo"]),
        queue=deps["queue"],
        token_validator=deps["token_validator"],
    )
    app.include_router(webhook_message.router)
    return app


def _valid_body() -> dict:
    return {
        "account_id": 1,
        "conversation_id": 42,
        "inbox_id": 10,
        "contact_id": 7,
        "contact_phone": "11987654321",
        "message_id": "m-1",
        "text": "preciso de ajuda",
        "occurred_at": "2026-04-17T10:00:00Z",
    }


def test_message_endpoint_enqueues():
    deps = {
        "dedup": AsyncMock(),
        "event_repo": AsyncMock(),
        "queue": AsyncMock(),
        "token_validator": AsyncMock(return_value=True),
    }
    deps["dedup"].try_mark = AsyncMock(return_value=True)
    deps["event_repo"].insert_if_new = AsyncMock(return_value=object())
    deps["queue"].enqueue = AsyncMock(return_value="j-1")
    client = TestClient(_make_app(deps))

    r = client.post(
        "/webhook/message",
        json=_valid_body(),
        headers={"Authorization": "Bearer nxia_test"},
    )
    assert r.status_code == 202
    deps["queue"].enqueue.assert_awaited_once()


def test_message_endpoint_rejects_invalid_token():
    deps = {
        "dedup": AsyncMock(),
        "event_repo": AsyncMock(),
        "queue": AsyncMock(),
        "token_validator": AsyncMock(return_value=False),
    }
    client = TestClient(_make_app(deps))
    r = client.post(
        "/webhook/message",
        json=_valid_body(),
        headers={"Authorization": "Bearer wrong"},
    )
    assert r.status_code == 401


def test_message_endpoint_rejects_missing_auth():
    deps = {
        "dedup": AsyncMock(),
        "event_repo": AsyncMock(),
        "queue": AsyncMock(),
        "token_validator": AsyncMock(return_value=True),
    }
    client = TestClient(_make_app(deps))
    r = client.post("/webhook/message", json=_valid_body())
    assert r.status_code == 401


def test_payload_rejects_missing_inbox_id():
    from pydantic import ValidationError

    from shared.adapters.chatnexo.schemas import IncomingMessagePayload

    body = _valid_body()
    del body["inbox_id"]
    with pytest.raises(ValidationError):
        IncomingMessagePayload(**body)


def test_payload_has_correct_fields():
    from shared.adapters.chatnexo.schemas import IncomingMessagePayload

    fields = IncomingMessagePayload.model_fields
    assert "inbox_id" in fields
    assert "message_id" in fields
    assert "media_urls" not in fields
    assert "classification_hint" not in fields
    assert "chatnexo_message_id" not in fields
