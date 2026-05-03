from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, insert, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shared.adapters.db.models import JobDlqModel, JobQueueModel
from shared.adapters.observability.logger import get_logger
from shared.domain.value_objects.priority import Priority

log = get_logger(__name__)

_DEQUEUE_SQL = text("""
    DELETE FROM job_queue
    WHERE id = (
        SELECT id FROM job_queue
        ORDER BY priority ASC, created_at ASC
        LIMIT 1
        FOR UPDATE SKIP LOCKED
    )
    RETURNING id, kind, payload, attempt
""")


@dataclass
class PostgresJobQueue:
    """Job queue backed by PostgreSQL using DELETE … RETURNING FOR UPDATE SKIP LOCKED.

    Envelope shape (identical to PriorityQueue):
        {"id": str, "payload": {"kind": str, "payload": dict}, "attempt": int}
    """

    sessionmaker: async_sessionmaker[AsyncSession]
    poll_interval: float = 0.2

    async def enqueue(
        self, payload: dict[str, Any], *, priority: Priority = Priority.NORMAL
    ) -> str:
        kind = payload.get("kind", "")
        inner = payload.get("payload", {})
        job_id = str(uuid.uuid4())
        async with self.sessionmaker() as session:
            await session.execute(
                insert(JobQueueModel).values(
                    id=uuid.UUID(job_id),
                    kind=kind,
                    payload=inner,
                    attempt=1,
                    last_error=None,
                    priority=priority.score,
                )
            )
            await session.commit()
        log.debug("job_queue_enqueued", kind=kind, job_id=job_id)
        return job_id

    async def dequeue(self, *, timeout: int = 5) -> dict[str, Any] | None:
        loop = asyncio.get_event_loop()
        deadline = loop.time() + timeout
        while True:
            async with self.sessionmaker() as session:
                result = await session.execute(_DEQUEUE_SQL)
                row = result.fetchone()
                await session.commit()
            if row is not None:
                return {
                    "id": str(row.id),
                    "payload": {"kind": row.kind, "payload": row.payload},
                    "attempt": row.attempt,
                }
            remaining = deadline - loop.time()
            if remaining <= 0:
                return None
            await asyncio.sleep(min(self.poll_interval, remaining))

    async def nack(self, envelope: dict[str, Any], *, error: str) -> None:
        inner = envelope.get("payload", {})
        kind = inner.get("kind", "")
        inner_payload = inner.get("payload", {})
        new_attempt = envelope.get("attempt", 1) + 1
        async with self.sessionmaker() as session:
            await session.execute(
                insert(JobQueueModel).values(
                    id=uuid.uuid4(),
                    kind=kind,
                    payload=inner_payload,
                    attempt=new_attempt,
                    last_error=error,
                    priority=Priority.NORMAL.score,
                )
            )
            await session.commit()
        log.debug("job_queue_nack", kind=kind, attempt=new_attempt)

    async def to_dlq(self, envelope: dict[str, Any], *, error: str) -> None:
        inner = envelope.get("payload", {})
        kind = inner.get("kind", "")
        inner_payload = inner.get("payload", {})
        async with self.sessionmaker() as session:
            await session.execute(
                insert(JobDlqModel).values(
                    id=uuid.uuid4(),
                    kind=kind,
                    payload=inner_payload,
                    attempt=envelope.get("attempt", 1),
                    last_error=error,
                )
            )
            await session.commit()
        log.warning("job_queue_dlq", kind=kind, error=error)

    async def depth(self) -> int:
        async with self.sessionmaker() as session:
            result = await session.execute(
                select(func.count()).select_from(JobQueueModel)
            )
            return int(result.scalar() or 0)
