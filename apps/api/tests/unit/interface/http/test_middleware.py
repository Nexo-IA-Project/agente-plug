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
    client = TestClient(_app_echoing_context())
    r = client.get("/echo", headers={"X-Correlation-Id": "fixed-123"})
    assert r.json()["cid"] == "fixed-123"
    assert r.headers["x-correlation-id"] == "fixed-123"
