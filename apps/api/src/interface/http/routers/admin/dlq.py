from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import delete, func, select

from shared.adapters.db.models import JobDlqModel, JobQueueModel
from shared.adapters.db.session import session_scope
from shared.config.settings import get_settings

router = APIRouter(tags=["admin-dlq"])


def _require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    if x_api_key != get_settings().admin_api_key:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid API key")


class DlqEntryOut(BaseModel):
    id: str
    kind: str
    payload: dict[str, Any]
    attempt: int
    last_error: str | None
    created_at: str


class DlqListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[DlqEntryOut]


class RequeueResponse(BaseModel):
    requeued: int


@router.get("/dlq", response_model=DlqListResponse, dependencies=[Depends(_require_api_key)])
async def list_dlq(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> DlqListResponse:
    """List dead-letter queue entries, most recent first."""
    offset = (page - 1) * page_size

    async with session_scope() as session:
        total_result = await session.execute(select(func.count()).select_from(JobDlqModel))
        total = int(total_result.scalar_one())

        result = await session.execute(
            select(JobDlqModel)
            .order_by(JobDlqModel.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        rows = result.scalars().all()

    items = [
        DlqEntryOut(
            id=str(row.id),
            kind=row.kind,
            payload=dict(row.payload),
            attempt=row.attempt,
            last_error=row.last_error,
            created_at=row.created_at.isoformat() if row.created_at else "",
        )
        for row in rows
    ]
    return DlqListResponse(total=total, page=page, page_size=page_size, items=items)


@router.delete(
    "/dlq/{entry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(_require_api_key)],
)
async def delete_dlq_entry(entry_id: str) -> None:
    """Remove a specific DLQ entry."""
    try:
        entry_uuid = uuid.UUID(entry_id)
    except ValueError:
        raise HTTPException(  # noqa: B904
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid entry ID"
        )

    async with session_scope() as session:
        result = await session.execute(
            delete(JobDlqModel).where(JobDlqModel.id == entry_uuid).returning(JobDlqModel.id)
        )
        deleted = result.fetchone()

    if deleted is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="DLQ entry not found")


@router.post(
    "/dlq/{entry_id}/requeue",
    response_model=RequeueResponse,
    dependencies=[Depends(_require_api_key)],
)
async def requeue_dlq_entry(entry_id: str) -> RequeueResponse:
    """Move a DLQ entry back to the job queue for reprocessing."""
    try:
        entry_uuid = uuid.UUID(entry_id)
    except ValueError:
        raise HTTPException(  # noqa: B904
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid entry ID"
        )

    async with session_scope() as session:
        result = await session.execute(select(JobDlqModel).where(JobDlqModel.id == entry_uuid))
        entry = result.scalar_one_or_none()
        if entry is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="DLQ entry not found")

        session.add(
            JobQueueModel(
                id=uuid.uuid4(),
                kind=entry.kind,
                payload=entry.payload,
                attempt=1,
                priority=20,
            )
        )
        await session.execute(delete(JobDlqModel).where(JobDlqModel.id == entry_uuid))

    return RequeueResponse(requeued=1)


@router.post(
    "/dlq/requeue-all",
    response_model=RequeueResponse,
    dependencies=[Depends(_require_api_key)],
)
async def requeue_all_dlq() -> RequeueResponse:
    """Move all DLQ entries back to the job queue."""
    async with session_scope() as session:
        result = await session.execute(select(JobDlqModel))
        entries = result.scalars().all()
        count = len(entries)

        for entry in entries:
            session.add(
                JobQueueModel(
                    id=uuid.uuid4(),
                    kind=entry.kind,
                    payload=entry.payload,
                    attempt=1,
                    priority=20,
                )
            )
        if entries:
            await session.execute(delete(JobDlqModel))

    return RequeueResponse(requeued=count)
