from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

from shared.adapters.redis.mutex import MutexAcquisitionError, RedisMutex

__all__ = ["LeadLock", "LeadLockError"]


class LeadLockError(RuntimeError):
    """Raised when a lead lock cannot be acquired within the timeout."""


@dataclass
class LeadLock:
    """Redis-based per-lead mutual exclusion.

    Prevents concurrent processing of messages from the same lead
    (identified by account_id + phone).
    """

    mutex: RedisMutex
    ttl_seconds: int = 60
    timeout: float = 30.0
    _retry_delay: float = field(default=0.05, init=False, repr=False)

    @asynccontextmanager
    async def acquire(self, *, account_id: str, phone: str) -> AsyncIterator[None]:
        key = f"lead:{account_id}:{phone}"
        try:
            async with self.mutex.acquire(
                key=key,
                ttl_seconds=self.ttl_seconds,
                timeout=self.timeout,
                retry_delay=self._retry_delay,
            ):
                yield
        except MutexAcquisitionError as exc:
            raise LeadLockError(
                f"Could not acquire lead lock for {account_id}:{phone} within {self.timeout}s"
            ) from exc
