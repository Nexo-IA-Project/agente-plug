from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from redis.asyncio import Redis


@dataclass
class DeadLetterEntry:
    job_id: str
    kind: str
    payload: dict[str, Any]
    attempt: int
    error: str
    failed_at: str


@dataclass
class DeadLetterQueue:
    redis: Redis
    name: str

    @property
    def _key(self) -> str:
        return f"dlq:{self.name}"

    async def push(self, entry: DeadLetterEntry) -> None:
        await self.redis.rpush(self._key, json.dumps(entry.__dict__))

    async def drain(self) -> list[DeadLetterEntry]:
        """Pop and return all entries currently in the DLQ."""
        entries: list[DeadLetterEntry] = []
        while True:
            raw = await self.redis.lpop(self._key)
            if raw is None:
                break
            data = json.loads(raw)
            entries.append(
                DeadLetterEntry(
                    job_id=data.get("job_id", ""),
                    kind=data.get("kind", ""),
                    payload=data.get("payload", {}),
                    attempt=int(data.get("attempt", 1)),
                    error=data.get("error", data.get("last_error", "")),
                    failed_at=data.get("failed_at", ""),
                )
            )
        return entries

    async def depth(self) -> int:
        return int(await self.redis.llen(self._key))

    @staticmethod
    def from_envelope(envelope: dict[str, Any], *, error: str) -> DeadLetterEntry:
        """Build a DeadLetterEntry from a queue envelope."""
        inner = dict(envelope.get("payload", {}))
        kind = str(inner.get("kind", ""))
        payload = dict(inner.get("payload", inner))
        return DeadLetterEntry(
            job_id=str(envelope.get("id", "")),
            kind=kind,
            payload=payload,
            attempt=int(envelope.get("attempt", 1)),
            error=error,
            failed_at=datetime.now(tz=UTC).isoformat(),
        )
