"""Testes do webhook /webhook/purchase com payload Hubla v2.

Estes testes usam TestClient + dependências mockadas — não tocam DB real (que
seria caro para validação de roteamento). Validam o contrato HTTP completo
(401, 202, 422, duplicate) e o enfileiramento.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from interface.http.errors import register_error_handlers
from interface.http.middleware import CorrelationIdMiddleware
from interface.http.routers import webhook_purchase


def _v2_payload(
    *,
    purchase_id: str = "sub-uuid-1",
    product_id: str = "QaIlGtff9tlU94JjDKSq",
) -> dict:
    return {
        "type": "subscription.activated",
        "version": "2.0.0",
        "event": {
            "product": {"id": product_id, "name": "X"},
            "products": [{"id": product_id, "name": "X"}],
            "subscription": {
                "id": purchase_id,
                "payer": {
                    "firstName": "Test",
                    "lastName": "User",
                    "document": "00000000000",
                    "email": "test@example.com",
                    "phone": "+5511999999999",
                },
                "activatedAt": "2026-05-02T02:59:25Z",
            },
            "user": {
                "id": "u1",
                "email": "test@example.com",
                "phone": "+5511999999999",
            },
        },
    }


@pytest.fixture
def app_and_deps():
    deps = {
        "dedup": AsyncMock(),
        "event_repo": AsyncMock(),
        "queue": AsyncMock(),
    }
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
    return app, deps


def test_webhook_subscription_activated_enqueues_job(app_and_deps):
    app, deps = app_and_deps
    deps["dedup"].try_mark = AsyncMock(return_value=True)
    deps["event_repo"].insert_if_new = AsyncMock(return_value=object())
    deps["queue"].enqueue = AsyncMock(return_value="job-1")

    client = TestClient(app)
    payload = _v2_payload()
    r = client.post(
        "/webhook/purchase",
        json=payload,
        headers={"x-hubla-token": "secret-token"},
    )
    assert r.status_code == 202, r.text
    assert r.json()["accepted"] is True
    assert r.json()["duplicate"] is False

    # Job enfileirado com o payload BRUTO (worker parseia de novo).
    deps["queue"].enqueue.assert_awaited_once()
    enqueued_arg = deps["queue"].enqueue.await_args.args[0]
    assert enqueued_arg["kind"] == "purchase"
    assert enqueued_arg["payload"]["type"] == "subscription.activated"
    assert (
        enqueued_arg["payload"]["event"]["subscription"]["id"]
        == payload["event"]["subscription"]["id"]
    )


def test_webhook_duplicate_subscription_returns_202_duplicate(app_and_deps):
    app, deps = app_and_deps
    # Dedup retorna False = já visto.
    deps["dedup"].try_mark = AsyncMock(return_value=False)
    deps["queue"].enqueue = AsyncMock()

    client = TestClient(app)
    r1 = client.post(
        "/webhook/purchase",
        json=_v2_payload(purchase_id="dup-1"),
        headers={"x-hubla-token": "secret-token"},
    )
    assert r1.status_code == 202
    assert r1.json()["duplicate"] is True
    deps["queue"].enqueue.assert_not_awaited()


def test_webhook_invalid_token_returns_401(app_and_deps):
    app, _deps = app_and_deps
    client = TestClient(app)
    r = client.post(
        "/webhook/purchase",
        json={"type": "subscription.activated", "event": {}},
        headers={"x-hubla-token": "wrong"},
    )
    assert r.status_code == 401
