from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from interface.http.errors import register_error_handlers
from interface.http.middleware import CorrelationIdMiddleware
from interface.http.routers import webhook_purchase


@pytest.fixture
def deps():
    return {
        "dedup": AsyncMock(),
        "event_repo": AsyncMock(),
        "queue": AsyncMock(),
    }


def _make_app(deps) -> FastAPI:
    app = FastAPI()
    app.add_middleware(CorrelationIdMiddleware)
    register_error_handlers(app)
    webhook_purchase.configure(
        dedup=deps["dedup"],
        event_repo_factory=lambda: deps["event_repo"],
        queue=deps["queue"],
        expected_token="secret-token",
    )
    app.include_router(webhook_purchase.router)
    return app


def _v2_payload(purchase_id: str = "p-1", product_id: str = "prod-x") -> dict:
    return {
        "type": "subscription.activated",
        "version": "2.0.0",
        "event": {
            "product": {"id": product_id, "name": "Curso X"},
            "products": [{"id": product_id, "name": "Curso X"}],
            "subscription": {
                "id": purchase_id,
                "payer": {
                    "firstName": "Ana",
                    "lastName": "Silva",
                    "document": "00000000000",
                    "email": "ana@test.com",
                    "phone": "+5511999887766",
                },
                "activatedAt": "2026-04-17T10:00:00Z",
            },
            "user": {"id": "u1", "email": "ana@test.com", "phone": "+5511999887766"},
        },
    }


def test_returns_401_without_token(deps):
    client = TestClient(_make_app(deps))
    r = client.post("/webhook/purchase", json={})
    assert r.status_code == 401


def test_returns_202_on_first_valid_call(deps):
    deps["dedup"].try_mark = AsyncMock(return_value=True)
    deps["event_repo"].insert_if_new = AsyncMock(return_value=object())
    deps["queue"].enqueue = AsyncMock(return_value="job-1")

    client = TestClient(_make_app(deps))
    r = client.post(
        "/webhook/purchase",
        json=_v2_payload(purchase_id="p-1", product_id="prod-x"),
        params={"token": "secret-token"},
    )
    assert r.status_code == 202, r.text
    deps["queue"].enqueue.assert_awaited_once()


def test_returns_202_but_skips_enqueue_on_duplicate(deps):
    deps["dedup"].try_mark = AsyncMock(return_value=False)
    deps["queue"].enqueue = AsyncMock()
    client = TestClient(_make_app(deps))
    r = client.post(
        "/webhook/purchase",
        json=_v2_payload(purchase_id="p-dup", product_id="prod-y"),
        params={"token": "secret-token"},
    )
    assert r.status_code == 202
    assert r.json()["duplicate"] is True
    deps["queue"].enqueue.assert_not_awaited()


def test_returns_422_on_invalid_payload(deps):
    """Payload sem 'type' subscription.activated deve retornar 422."""
    deps["dedup"].try_mark = AsyncMock(return_value=True)
    client = TestClient(_make_app(deps))
    r = client.post(
        "/webhook/purchase",
        json={"type": "subscription.canceled", "event": {}},
        params={"token": "secret-token"},
    )
    assert r.status_code == 422
