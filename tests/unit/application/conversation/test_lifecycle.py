import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

from nexoia.application.conversation.lifecycle import (
    ConversationLifecycleManager,
)
from nexoia.domain.entities.conversation import Conversation, ConversationStatus, IdleState
from nexoia.domain.entities.scheduled_job import JobType
from nexoia.infrastructure.clock.system_clock import FrozenClock


def _conv(**overrides) -> Conversation:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    base = dict(
        id=uuid.uuid4(),
        account_id=uuid.uuid4(),
        contact_id=uuid.uuid4(),
        chatnexo_conversation_id=1,
        status=ConversationStatus.ACTIVE,
        last_activity_at=now,
        window_expires_at=now + timedelta(hours=24),
        handoff_reason=None,
        idle_state=IdleState.NONE,
    )
    base.update(overrides)
    return Conversation(**base)


def test_variation_is_deterministic_per_conversation() -> None:
    mgr = ConversationLifecycleManager(
        scheduled_repo=AsyncMock(),
        conv_repo=AsyncMock(),
        chatnexo=AsyncMock(),
        clock=FrozenClock(datetime(2026, 1, 1, tzinfo=UTC)),
        ping_minutes=30,
        close_minutes=20,
    )
    conv_id = uuid.UUID("12345678-1234-1234-1234-123456789012")
    a = mgr._pick_variation(conv_id, "ping", name="Ana")
    b = mgr._pick_variation(conv_id, "ping", name="Ana")
    assert a == b  # same input → same output


async def test_schedule_idle_ping_after_agent_message() -> None:
    scheduled = AsyncMock()
    scheduled.cancel_by_conversation = AsyncMock(return_value=0)
    scheduled.schedule = AsyncMock()
    clock = FrozenClock(datetime(2026, 1, 1, 10, 0, tzinfo=UTC))

    mgr = ConversationLifecycleManager(
        scheduled_repo=scheduled,
        conv_repo=AsyncMock(),
        chatnexo=AsyncMock(),
        clock=clock,
        ping_minutes=30,
        close_minutes=20,
    )
    conv = _conv()
    await mgr.on_agent_outbound(conversation=conv, correlation_id="c-1")

    scheduled.cancel_by_conversation.assert_awaited_once()
    call = scheduled.schedule.await_args
    assert call.kwargs["job_type"] == JobType.IDLE_PING
    assert call.kwargs["run_at"] == datetime(2026, 1, 1, 10, 30, tzinfo=UTC)


async def test_fire_ping_skips_when_handed_off() -> None:
    chatnexo = AsyncMock()
    conv_repo = AsyncMock()
    scheduled = AsyncMock()
    mgr = ConversationLifecycleManager(
        scheduled_repo=scheduled,
        conv_repo=conv_repo,
        chatnexo=chatnexo,
        clock=FrozenClock(datetime(2026, 1, 1, tzinfo=UTC)),
        ping_minutes=30,
        close_minutes=20,
    )
    conv = _conv(status=ConversationStatus.HANDED_OFF)
    await mgr.fire_ping(conversation=conv, contact_name="Ana", correlation_id="c")
    chatnexo.send_message.assert_not_awaited()
    scheduled.schedule.assert_not_awaited()


async def test_fire_ping_sends_message_and_schedules_close() -> None:
    chatnexo = AsyncMock()
    conv_repo = AsyncMock()
    scheduled = AsyncMock()
    clock = FrozenClock(datetime(2026, 1, 1, 10, 0, tzinfo=UTC))
    mgr = ConversationLifecycleManager(
        scheduled_repo=scheduled,
        conv_repo=conv_repo,
        chatnexo=chatnexo,
        clock=clock,
        ping_minutes=30,
        close_minutes=20,
    )
    conv = _conv()
    await mgr.fire_ping(conversation=conv, contact_name="Ana", correlation_id="c")

    chatnexo.send_message.assert_awaited_once()
    assert conv.idle_state == IdleState.PING_SENT

    scheduled.schedule.assert_awaited_once()
    assert scheduled.schedule.await_args.kwargs["job_type"] == JobType.IDLE_CLOSE
    assert scheduled.schedule.await_args.kwargs["run_at"] == datetime(
        2026, 1, 1, 10, 20, tzinfo=UTC
    )


async def test_fire_close_sends_message_and_marks_closed() -> None:
    chatnexo = AsyncMock()
    conv_repo = AsyncMock()
    clock = FrozenClock(datetime(2026, 1, 1, tzinfo=UTC))
    mgr = ConversationLifecycleManager(
        scheduled_repo=AsyncMock(),
        conv_repo=conv_repo,
        chatnexo=chatnexo,
        clock=clock,
        ping_minutes=30,
        close_minutes=20,
    )
    conv = _conv(idle_state=IdleState.PING_SENT)
    await mgr.fire_close(conversation=conv, contact_name="Ana", correlation_id="c")

    chatnexo.send_message.assert_awaited_once()
    assert conv.status == ConversationStatus.CLOSED_BY_TIMEOUT
    assert conv.idle_state == IdleState.CLOSED


async def test_fire_close_skips_if_outside_24h_window_but_still_marks_closed() -> None:
    chatnexo = AsyncMock()
    clock = FrozenClock(datetime(2026, 1, 2, 12, 0, tzinfo=UTC))
    mgr = ConversationLifecycleManager(
        scheduled_repo=AsyncMock(),
        conv_repo=AsyncMock(),
        chatnexo=chatnexo,
        clock=clock,
        ping_minutes=30,
        close_minutes=20,
    )
    conv = _conv(
        window_expires_at=datetime(2026, 1, 2, 11, 0, tzinfo=UTC),
        idle_state=IdleState.PING_SENT,
    )
    await mgr.fire_close(conversation=conv, contact_name="Ana", correlation_id="c")
    chatnexo.send_message.assert_not_awaited()
    assert conv.status == ConversationStatus.CLOSED_BY_TIMEOUT
