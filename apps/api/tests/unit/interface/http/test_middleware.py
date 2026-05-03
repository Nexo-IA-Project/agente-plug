from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from interface.http.middleware import (
    CorrelationIdMiddleware,
    correlation_id_var,
)


def _app_echoing_context() -> FastAPI:
    app = FastAPI()
    app.add_middleware(CorrelationIdMiddleware)

    @app.get("/echo")
    async def echo(request: Request):
        return {"cid": correlation_id_var.get()}

    return app


def test_correlation_id_is_generated_when_missing() -> None:
    client = TestClient(_app_echoing_context())
    r = client.get("/echo")
    body = r.json()
    assert body["cid"]
    assert r.headers["x-correlation-id"] == body["cid"]


def test_correlation_id_is_preserved_from_header() -> None:
    valid_cid = "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4"  # valid 32-char hex
    client = TestClient(_app_echoing_context())
    r = client.get("/echo", headers={"X-Correlation-Id": valid_cid})
    assert r.json()["cid"] == valid_cid
    assert r.headers["x-correlation-id"] == valid_cid


def test_invalid_correlation_id_is_replaced() -> None:
    client = TestClient(_app_echoing_context())
    r = client.get("/echo", headers={"X-Correlation-Id": "invalid-id"})
    # should generate a new valid hex UUID, not keep the invalid value
    assert r.json()["cid"] != "invalid-id"
    assert len(r.json()["cid"]) == 32
