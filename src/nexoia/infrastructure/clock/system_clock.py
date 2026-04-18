from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


@dataclass
class FrozenClock:
    current: datetime

    def now(self) -> datetime:
        return self.current

    def advance(self, *, seconds: int = 0, minutes: int = 0, hours: int = 0) -> None:
        self.current += timedelta(seconds=seconds, minutes=minutes, hours=hours)
