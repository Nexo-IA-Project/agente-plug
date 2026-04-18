from datetime import UTC, datetime

from freezegun import freeze_time

from nexoia.infrastructure.clock.system_clock import FrozenClock, SystemClock


def test_system_clock_returns_utc_now() -> None:
    with freeze_time("2026-01-01T10:00:00Z"):
        now = SystemClock().now()
    assert now == datetime(2026, 1, 1, 10, 0, tzinfo=UTC)


def test_frozen_clock_returns_provided_time() -> None:
    t = datetime(2026, 1, 1, tzinfo=UTC)
    clock = FrozenClock(t)
    assert clock.now() == t

    clock.advance(seconds=60)
    assert clock.now() == datetime(2026, 1, 1, 0, 1, tzinfo=UTC)
