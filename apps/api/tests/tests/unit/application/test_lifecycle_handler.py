from __future__ import annotations
import pytest
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from nexoia.application.lifecycle_handler import LifecycleHandler


def fake_conv(status: str = "ACTIVE", window_ok: bool = True):
    conv = MagicMock()
    conv.status = status
    conv.window_expires_at = (
        datetime.now(UTC) + timedelta(hours=1)
        if window_ok
        else datetime.now(UTC) - timedelta(hours=1)
    )
    return conv


def fake_contact(name: str = "João"):
    c = MagicMock()
    c.name = name
    return c


@pytest.mark.asyncio
async def test_send_ping_sends_message_when_conv_active():
    conv_repo = AsyncMock()
    conv_repo.find_active.return_value = fake_conv()
    contact_repo = AsyncMock()
    contact_repo.find_by_phone.return_value = fake_contact()
    chatnexo = AsyncMock()
    scheduler = AsyncMock()
    handler = LifecycleHandler(
        conv_repo=conv_repo,
        contact_repo=contact_repo,
        chatnexo=chatnexo,
        scheduler=scheduler,
    )
    await handler.send_ping(account_id="t1", phone="5511999", conversation_id="c1")
    chatnexo.send_message.assert_called_once()
    scheduler.create_job.assert_called_once()


@pytest.mark.asyncio
async def test_send_ping_skips_when_conv_handed_off():
    conv_repo = AsyncMock()
    conv_repo.find_active.return_value = fake_conv(status="HANDED_OFF")
    chatnexo = AsyncMock()
    scheduler = AsyncMock()
    handler = LifecycleHandler(
        conv_repo=conv_repo,
        contact_repo=AsyncMock(),
        chatnexo=chatnexo,
        scheduler=scheduler,
    )
    await handler.send_ping(account_id="t1", phone="5511999", conversation_id="c1")
    chatnexo.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_send_close_closes_conversation():
    conv_repo = AsyncMock()
    conv_repo.find_active.return_value = fake_conv(status="IDLE_PINGED")
    contact_repo = AsyncMock()
    contact_repo.find_by_phone.return_value = fake_contact("Maria")
    chatnexo = AsyncMock()
    handler = LifecycleHandler(
        conv_repo=conv_repo,
        contact_repo=contact_repo,
        chatnexo=chatnexo,
        scheduler=AsyncMock(),
    )
    await handler.send_close(account_id="t1", phone="5511999", conversation_id="c1")
    chatnexo.send_message.assert_called_once()
    conv_repo.update_status.assert_called_once()
