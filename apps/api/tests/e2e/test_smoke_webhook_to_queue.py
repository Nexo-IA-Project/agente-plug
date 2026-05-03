"""E2E smoke: valida que o webhook Hubla enfileira job e /health responde."""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer


@pytest.fixture(scope="module")
def pg_container():
    with PostgresContainer("pgvector/pgvector:pg16") as c:
        yield c


@pytest.fixture(scope="module")
def redis_container():
    with RedisContainer("redis:7-alpine") as c:
        yield c


@pytest.mark.e2e
def test_purchase_webhook_enqueues_job(
    pg_container: PostgresContainer,
    redis_container: RedisContainer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_url = pg_container.get_connection_url().replace("psycopg2", "asyncpg")
    redis_url = (
        f"redis://{redis_container.get_container_host_ip()}:"
        f"{redis_container.get_exposed_port(6379)}/0"
    )
    env = {
        "DATABASE_URL": db_url,
        "REDIS_URL": redis_url,
        "OPENAI_API_KEY": "sk-x",
        "CHATNEXO_BASE_URL": "http://localhost:9999",
        "CHATNEXO_API_KEY": "cn-secret",
        "HUBLA_WEBHOOK_SECRET": "hubla-secret",
        "ADMIN_API_KEY": "admin-secret",
        "META_API_KEY": "meta-x",
        "INTEGRATION_CREDENTIALS_KEY": "YEqfuO1aT0ibxW5p3oACqKm4sVqlKwpz9wZ0qCc0Yfs=",
    }
    for k, v in env.items():
        monkeypatch.setenv(k, v)

    import importlib

    import main.config.settings as st

    importlib.reload(st)
    import main.main as m

    importlib.reload(m)

    # Run alembic migrations up
    from alembic import command
    from alembic.config import Config as AlembicConfig

    cfg = AlembicConfig("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(cfg, "heads")

    client = TestClient(m.app)

    r = client.get("/health")
    assert r.status_code == 200

    body = {
        "purchase_id": "e2e-1",
        "account_id": 1,
        "name": "Ana",
        "email": "ana@t.com",
        "phone": "11987654321",
        "product": "Curso X",
        "amount_brl": 19700,
        "occurred_at": "2026-04-17T10:00:00Z",
    }
    r = client.post("/webhook/purchase", json=body, headers={"X-Hubla-Token": "hubla-secret"})
    assert r.status_code == 202
    assert r.json()["duplicate"] is False

    # Queue should have 1 job in job_queue table
    async def _depth() -> int:
        engine = create_async_engine(db_url)
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT COUNT(*) FROM job_queue"))
            count = result.scalar()
        await engine.dispose()
        return int(count or 0)

    assert asyncio.run(_depth()) == 1

    # Duplicate call should be accepted but not enqueue
    r2 = client.post("/webhook/purchase", json=body, headers={"X-Hubla-Token": "hubla-secret"})
    assert r2.status_code == 202
    assert r2.json()["duplicate"] is True
    assert asyncio.run(_depth()) == 1
