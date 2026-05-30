"""Testes do webhook /webhook/hubla (roteador unificado de eventos Hubla).

Usa TestClient + dependências mockadas — não toca DB real.
Valida o contrato HTTP completo: 401, 202, dedup, event namespace.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from interface.http.errors import register_error_handlers
from interface.http.middleware import CorrelationIdMiddleware
from interface.http.routers import webhook_hubla


@asynccontextmanager
async def _repo_cm(repo):
    yield repo


async def _token_resolver_secret() -> str:
    return "secret-token"


def _activated_payload(
    *,
    subscription_id: str = "sub-uuid-1",
    product_id: str = "prod-abc123",
) -> dict:
    return {
        "type": "subscription.activated",
        "version": "2.0.0",
        "event": {
            "product": {"id": product_id, "name": "Curso Exemplo"},
            "products": [{"id": product_id, "name": "Curso Exemplo"}],
            "subscription": {
                "id": subscription_id,
                "payer": {
                    "firstName": "Test",
                    "lastName": "User",
                    "document": "00000000000",
                    "email": "test@example.com",
                    "phone": "+5511999999999",
                },
                "activatedAt": "2026-05-22T10:00:00Z",
            },
            "user": {
                "id": "u1",
                "email": "test@example.com",
                "phone": "+5511999999999",
            },
        },
    }


def _non_purchase_payload(
    *,
    event_type: str = "lead.abandoned",
    subscription_id: str = "lead-uuid-1",
    product_id: str = "prod-abc123",
) -> dict:
    return {
        "type": event_type,
        "version": "2.0.0",
        "event": {
            "product": {"id": product_id, "name": "Curso Exemplo"},
            "subscription": {
                "id": subscription_id,
                "payer": {
                    "firstName": "Lead",
                    "lastName": "Person",
                    "email": "lead@example.com",
                    "phone": "+5511888888888",
                },
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
    webhook_hubla.configure(
        dedup=deps["dedup"],
        event_repo_factory=lambda: _repo_cm(deps["event_repo"]),
        queue=deps["queue"],
        token_resolver=_token_resolver_secret,
    )
    app.include_router(webhook_hubla.router)
    return app, deps


def test_missing_token_returns_401(app_and_deps):
    app, _deps = app_and_deps
    client = TestClient(app)
    r = client.post("/webhook/hubla", json=_activated_payload())
    assert r.status_code == 401


def test_invalid_token_returns_401(app_and_deps):
    app, _deps = app_and_deps
    client = TestClient(app)
    r = client.post(
        "/webhook/hubla",
        json=_activated_payload(),
        params={"token": "wrong-token"},
    )
    assert r.status_code == 401


def test_valid_token_and_payload_enqueues_job(app_and_deps):
    app, deps = app_and_deps
    deps["dedup"].try_mark = AsyncMock(return_value=True)
    deps["event_repo"].insert_if_new = AsyncMock(return_value=object())
    deps["queue"].enqueue = AsyncMock(return_value="job-hubla-1")

    client = TestClient(app)
    payload = _activated_payload()
    r = client.post(
        "/webhook/hubla",
        json=payload,
        params={"token": "secret-token"},
    )

    assert r.status_code == 202, r.text
    body = r.json()
    assert body["accepted"] is True
    assert body["duplicate"] is False

    # Job enfileirado com o payload bruto (worker parseia de novo).
    deps["queue"].enqueue.assert_awaited_once()
    enqueued_arg = deps["queue"].enqueue.await_args.args[0]
    assert enqueued_arg["kind"] == "hubla_event"
    assert enqueued_arg["payload"]["type"] == "subscription.activated"
    assert (
        enqueued_arg["payload"]["event"]["subscription"]["id"]
        == payload["event"]["subscription"]["id"]
    )


def test_v1_newsale_uses_transaction_id_for_dedup_key(app_and_deps):
    """Regressão do incidente: NewSale (v1) não tem event.subscription.id — o id da
    venda está em event.transactionId. O external_id NÃO pode colapsar para 'NewSale'
    (senão o dedup derruba todas as vendas após a 1ª). Deve usar o transactionId."""
    app, deps = app_and_deps
    deps["dedup"].try_mark = AsyncMock(return_value=True)
    deps["event_repo"].insert_if_new = AsyncMock(return_value=object())
    deps["queue"].enqueue = AsyncMock(return_value="job-1")

    client = TestClient(app)
    payload = {"type": "NewSale", "version": "1.0.0", "event": {"transactionId": "tx-abc-123"}}
    r = client.post("/webhook/hubla", json=payload, params={"token": "secret-token"})

    assert r.status_code == 202, r.text
    assert r.json()["duplicate"] is False
    # chave de dedup deve conter o transactionId, não ser apenas "hubla:NewSale"
    key = deps["dedup"].try_mark.await_args.kwargs["key"]
    assert key == "hubla:NewSale:tx-abc-123"
    deps["queue"].enqueue.assert_awaited_once()


def test_v1_newsales_with_distinct_tx_are_not_deduped(app_and_deps):
    """Duas vendas NewSale com transactionId distintos geram chaves de dedup distintas."""
    app, deps = app_and_deps
    deps["dedup"].try_mark = AsyncMock(return_value=True)
    deps["event_repo"].insert_if_new = AsyncMock(return_value=object())
    deps["queue"].enqueue = AsyncMock(return_value="j")
    client = TestClient(app)
    for tx in ("tx-1", "tx-2"):
        client.post(
            "/webhook/hubla",
            json={"type": "NewSale", "version": "1.0.0", "event": {"transactionId": tx}},
            params={"token": "secret-token"},
        )
    keys = [c.kwargs["key"] for c in deps["dedup"].try_mark.await_args_list]
    assert keys == ["hubla:NewSale:tx-1", "hubla:NewSale:tx-2"]
    assert deps["queue"].enqueue.await_count == 2


def test_duplicate_payload_returns_202_duplicate_no_enqueue(app_and_deps):
    app, deps = app_and_deps
    # Dedup retorna False = já visto anteriormente.
    deps["dedup"].try_mark = AsyncMock(return_value=False)
    deps["queue"].enqueue = AsyncMock()

    client = TestClient(app)
    r = client.post(
        "/webhook/hubla",
        json=_activated_payload(subscription_id="dup-sub-1"),
        params={"token": "secret-token"},
    )

    assert r.status_code == 202
    body = r.json()
    assert body["accepted"] is True
    assert body["duplicate"] is True
    # Evento duplicado não deve ser enfileirado.
    deps["queue"].enqueue.assert_not_awaited()


def test_non_purchase_event_enqueues_with_different_namespace(app_and_deps):
    """lead.abandoned deve ser aceito e enfileirado (namespace diferente de subscription.activated)."""
    app, deps = app_and_deps
    deps["dedup"].try_mark = AsyncMock(return_value=True)
    deps["event_repo"].insert_if_new = AsyncMock(return_value=object())
    deps["queue"].enqueue = AsyncMock(return_value="job-lead-1")

    client = TestClient(app)
    payload = _non_purchase_payload(event_type="lead.abandoned", subscription_id="lead-uuid-99")
    r = client.post(
        "/webhook/hubla",
        json=payload,
        params={"token": "secret-token"},
    )

    assert r.status_code == 202, r.text
    body = r.json()
    assert body["accepted"] is True
    assert body["duplicate"] is False

    deps["queue"].enqueue.assert_awaited_once()
    enqueued_arg = deps["queue"].enqueue.await_args.args[0]
    assert enqueued_arg["kind"] == "hubla_event"
    assert enqueued_arg["payload"]["type"] == "lead.abandoned"

    # Dedup key deve usar o event_type correto (namespace separado de subscription.activated).
    dedup_call_kwargs = deps["dedup"].try_mark.await_args.kwargs
    assert "lead.abandoned" in dedup_call_kwargs["key"]
