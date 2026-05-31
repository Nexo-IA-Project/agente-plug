from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from interface.http.deps.admin_auth import AdminAuth
from interface.http.deps.permissions import require_permission
from shared.adapters.db.repositories.audit_repo import SqlAuditRepository
from shared.adapters.db.session import session_scope
from shared.application.use_cases.admin.list_audit_events import (
    ListAuditEventsInput,
    ListAuditEventsUseCase,
)
from shared.domain.entities.audit_event import AuditEvent

router = APIRouter(tags=["admin-audit"])


class AuditEventResponse(BaseModel):
    id: UUID
    user_name: str | None
    action: str
    resource_type: str
    resource_id: str | None
    ip_address: str | None
    geo_city: str | None
    geo_country: str | None
    geo_region: str | None
    created_at: datetime


class AuditEventListResponse(BaseModel):
    items: list[AuditEventResponse]
    total: int
    page: int
    page_size: int


def _to_response(e: AuditEvent) -> AuditEventResponse:
    return AuditEventResponse(
        id=e.id,
        user_name=e.user_name,
        action=e.action,
        resource_type=e.resource_type,
        resource_id=e.resource_id,
        ip_address=e.ip_address,
        geo_city=e.geo_city,
        geo_country=e.geo_country,
        geo_region=e.geo_region,
        created_at=e.created_at,
    )


@router.get("/audit-events", response_model=AuditEventListResponse)
async def list_audit_events(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    user_id: str | None = Query(default=None),
    action: str | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    auth: AdminAuth = Depends(require_permission("audit.view")),
) -> AuditEventListResponse:
    if auth.account_id is None:
        raise HTTPException(status_code=400, detail="account_id ausente no token")
    async with session_scope() as session:
        repo = SqlAuditRepository(session=session)
        use_case = ListAuditEventsUseCase(repo=repo)
        result = await use_case.execute(
            ListAuditEventsInput(
                account_id=auth.account_id,
                user_id=user_id,
                action=action,
                date_from=date_from,
                date_to=date_to,
                page=page,
                page_size=page_size,
            )
        )
    return AuditEventListResponse(
        items=[_to_response(e) for e in result.items],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
    )
