from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest


@pytest.mark.asyncio
async def test_publish_and_subscribe_roundtrip(redis_container_session, monkeypatch):
    """Publica envelope em um account e o receive-end recebe."""
    host = redis_container_session.get_container_host_ip()
    port = redis_container_session.get_exposed_port(6379)
    monkeypatch.setenv("REDIS_URL", f"redis://{host}:{port}/0")

    from shared.adapters.redis.leads_pubsub import LeadsPubSub
    from shared.config.settings import get_settings

    get_settings.cache_clear()

    account_id = uuid4()
    bus = LeadsPubSub()

    received: list[dict] = []

    async def consume():
        async for env in bus.subscribe(account_id):
            received.append(env)
            return

    task = asyncio.create_task(consume())
    await asyncio.sleep(0.2)  # esperar subscribe entrar
    await bus.publish(account_id, {"type": "lead.upserted", "lead": {"id": "x"}})
    await asyncio.wait_for(task, timeout=3.0)

    assert len(received) == 1
    assert received[0]["type"] == "lead.upserted"
    assert received[0]["lead"]["id"] == "x"

    await bus.close()


@pytest.mark.asyncio
async def test_publish_to_other_account_is_not_received(redis_container_session, monkeypatch):
    """Publica em account A; subscriber de B não recebe."""
    host = redis_container_session.get_container_host_ip()
    port = redis_container_session.get_exposed_port(6379)
    monkeypatch.setenv("REDIS_URL", f"redis://{host}:{port}/0")

    from shared.adapters.redis.leads_pubsub import LeadsPubSub
    from shared.config.settings import get_settings

    get_settings.cache_clear()

    account_a = uuid4()
    account_b = uuid4()
    bus = LeadsPubSub()

    received: list[dict] = []

    async def consume():
        async for env in bus.subscribe(account_b):
            received.append(env)
            return

    task = asyncio.create_task(consume())
    await asyncio.sleep(0.2)
    await bus.publish(account_a, {"type": "lead.upserted", "lead": {"id": "x"}})

    try:
        await asyncio.wait_for(task, timeout=1.0)
    except TimeoutError:
        task.cancel()

    assert received == []

    await bus.close()
