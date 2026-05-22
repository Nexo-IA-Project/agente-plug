"""Endpoints de relatório de enrollments para o painel admin.

- ``GET /admin/followup/enrollments`` — lista paginada com filtros.
- ``GET /admin/followup/enrollments/{id}/steps`` — steps de um enrollment com
  ``sent_at``, ``scheduled_for`` (vindo de ``scheduled_jobs.run_at``) e
  ``failure_reason``.
"""

from __future__ import annotations

import uuid as _uuid_module
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from pydantic import BaseModel
from sqlalchemy import select

from interface.http.deps.admin_auth import AdminAuth, require_admin
from shared.adapters.db.models import AccountModel
from shared.adapters.db.repositories.followup_enrollment_repo import (
    FollowupEnrollmentRepository,
)
from shared.adapters.db.session import session_scope
from shared.domain.entities.followup import EnrollmentStatus

router = APIRouter(tags=["admin-followup-reports"])


# ──────────────────────────────────────────────────────────────
# Schemas
# ──────────────────────────────────────────────────────────────


class EnrollmentListItem(BaseModel):
    id: str
    contact_phone: str
    customer_name: str | None
    flow_id: str | None
    flow_name: str | None
    product_name: str | None
    status: str
    created_at: str
    steps_sent: int
    steps_total: int


class EnrollmentListResponse(BaseModel):
    items: list[EnrollmentListItem]
    total: int
    page: int
    page_size: int


class EnrollmentStepItem(BaseModel):
    id: str
    position: int
    delay_from_purchase_minutes: int
    template_name: str | None
    message_text_preview: str | None
    status: str
    sent_at: str | None
    scheduled_for: str | None
    failure_reason: str | None


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────


async def _get_account_uuid(session, auth: AdminAuth) -> _uuid_module.UUID:
    """Resolve ``auth.account_id`` para o UUID do registro em ``accounts``.

    Sistema single-tenant: ``AdminAuth.account_id`` é um ``int`` (atualmente 1)
    e a tabela ``accounts`` usa UUID como PK sem coluna inteira correspondente.
    O lookup retorna o primeiro account encontrado. Quando multi-tenant chegar,
    esta função deve passar a mapear ``auth.account_id`` para o UUID correto.
    """
    _ = auth  # explicitar intenção single-tenant
    result = await session.execute(select(AccountModel.id).limit(1))
    return result.scalar_one()


# ──────────────────────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────────────────────


@router.get("/followup/enrollments", response_model=EnrollmentListResponse)
async def list_enrollments(
    flow_id: UUID | None = Query(default=None),  # noqa: B008
    contact_phone: str | None = Query(default=None),
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    auth: AdminAuth = Depends(require_admin),  # noqa: B008
) -> EnrollmentListResponse:
    status_enum: EnrollmentStatus | None = None
    if status:
        try:
            status_enum = EnrollmentStatus(status.lower())
        except ValueError as exc:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=f"invalid status: {status}",
            ) from exc

    async with session_scope() as session:
        account_uuid = await _get_account_uuid(session, auth)
        repo = FollowupEnrollmentRepository(session=session)
        rows, total = await repo.list_for_report(
            account_id=account_uuid,
            flow_id=flow_id,
            contact_phone=contact_phone,
            status=status_enum,
            page=page,
            page_size=page_size,
        )
        counts = await repo.bulk_count_steps([r.id for r in rows])

    items = [
        EnrollmentListItem(
            id=str(r.id),
            contact_phone=r.contact_phone,
            customer_name=r.customer_name,
            flow_id=str(r.flow_id) if r.flow_id else None,
            flow_name=r.flow_name,
            product_name=r.product_name,
            status=r.status.value,
            created_at=r.created_at.isoformat(),
            steps_sent=counts.get(r.id, {}).get("sent", 0),
            steps_total=sum(counts.get(r.id, {}).values()),
        )
        for r in rows
    ]
    return EnrollmentListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/followup/enrollments/{enrollment_id}/steps",
    response_model=list[EnrollmentStepItem],
)
async def list_enrollment_steps(
    enrollment_id: UUID,
    auth: AdminAuth = Depends(require_admin),  # noqa: B008
) -> list[EnrollmentStepItem]:
    async with session_scope() as session:
        account_uuid = await _get_account_uuid(session, auth)
        repo = FollowupEnrollmentRepository(session=session)
        steps = await repo.list_steps_for_report(
            enrollment_id,
            account_id=account_uuid,
        )
    return [
        EnrollmentStepItem(
            id=str(s.id),
            position=s.position,
            delay_from_purchase_minutes=s.delay_from_purchase_minutes,
            template_name=s.meta_template_name,
            message_text_preview=(s.message_text[:80] if s.message_text else None),
            status=s.status,
            sent_at=s.sent_at.isoformat() if s.sent_at else None,
            scheduled_for=s.scheduled_for.isoformat() if s.scheduled_for else None,
            failure_reason=s.failure_reason,
        )
        for s in steps
    ]
