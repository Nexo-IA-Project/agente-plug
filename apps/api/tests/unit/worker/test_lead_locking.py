"""Unit tests for LeadLock and handle_message lead-locking integration (Task 8)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from shared.adapters.redis.lead_lock import LeadLock, LeadLockError
from shared.adapters.redis.mutex import MutexAcquisitionError, RedisMutex

# ── LeadLock unit tests ───────────────────────────────────────────────────────


def _make_mutex(*, raises: bool = False) -> RedisMutex:
    mutex = MagicMock(spec=RedisMutex)

    if raises:

        @asynccontextmanager
        async def _acquire_fail(**kwargs: Any) -> AsyncIterator[None]:
            raise MutexAcquisitionError("timeout")
            yield  # make it a generator

        mutex.acquire = _acquire_fail
    else:

        @asynccontextmanager
        async def _acquire_ok(**kwargs: Any) -> AsyncIterator[None]:
            yield

        mutex.acquire = _acquire_ok

    return mutex


@pytest.mark.asyncio
async def test_lead_lock_acquire_yields_on_success() -> None:
    lock = LeadLock(mutex=_make_mutex())
    entered = False
    async with lock.acquire(account_id="acc-1", phone="+55"):
        entered = True
    assert entered


@pytest.mark.asyncio
async def test_lead_lock_raises_lead_lock_error_on_timeout() -> None:
    lock = LeadLock(mutex=_make_mutex(raises=True))
    with pytest.raises(LeadLockError):
        async with lock.acquire(account_id="acc-1", phone="+55"):
            pass


@pytest.mark.asyncio
async def test_lead_lock_key_includes_account_and_phone() -> None:
    acquired_key: list[str] = []

    @asynccontextmanager
    async def _capture(**kwargs: Any) -> AsyncIterator[None]:
        acquired_key.append(kwargs["key"])
        yield

    mutex = MagicMock(spec=RedisMutex)
    mutex.acquire = _capture

    lock = LeadLock(mutex=mutex)
    async with lock.acquire(account_id="acc-42", phone="+5511999"):
        pass

    assert acquired_key == ["lead:acc-42:+5511999"]


# ── handle_message integration with lock ─────────────────────────────────────


def _make_payload(
    account_id: str = "acc-1",
    phone: str = "+5511999",
    conversation_id: str = "conv-1",
    text: str = "Olá",
) -> dict[str, str]:
    return {
        "account_id": account_id,
        "phone": phone,
        "conversation_id": conversation_id,
        "text": text,
    }


@pytest.mark.asyncio
async def test_handle_message_acquires_lock_with_correct_lead() -> None:
    from interface.worker.handlers.message import handle_message

    acquired: list[dict[str, str]] = []

    @asynccontextmanager
    async def _capture(**kwargs: Any) -> AsyncIterator[None]:
        acquired.append({"account_id": kwargs["account_id"], "phone": kwargs["phone"]})
        raise NotImplementedError("stop here — we only test lock acquisition")
        yield

    lock = MagicMock(spec=LeadLock)
    lock.acquire = _capture

    with pytest.raises(NotImplementedError):
        await handle_message(_make_payload(), lead_lock=lock)

    assert acquired == [{"account_id": "acc-1", "phone": "+5511999"}]


@pytest.mark.asyncio
async def test_handle_message_without_lock_does_not_require_lead_lock() -> None:
    """When lead_lock=None the handler runs without locking (backward compat)."""
    from interface.worker.handlers.message import handle_message

    with (
        patch(
            "interface.worker.handlers.message._get_agent",
            side_effect=NotImplementedError("stub"),
        ),
        pytest.raises(NotImplementedError, match="stub"),
    ):
        await handle_message(_make_payload(), lead_lock=None)


@pytest.mark.asyncio
async def test_handle_message_propagates_lead_lock_error() -> None:
    from interface.worker.handlers.message import handle_message

    lock = MagicMock(spec=LeadLock)

    @asynccontextmanager
    async def _fail(**kwargs: Any) -> AsyncIterator[None]:
        raise LeadLockError("locked")
        yield

    lock.acquire = _fail

    with pytest.raises(LeadLockError, match="locked"):
        await handle_message(_make_payload(), lead_lock=lock)
