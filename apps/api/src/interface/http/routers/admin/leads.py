from __future__ import annotations

import csv
import io
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from interface.http.deps.admin_auth import AdminAuth, require_admin
from shared.adapters.db.repositories.lead_repo import SqlLeadRepository
from shared.adapters.db.session import session_scope
from shared.config.single_tenant import get_default_account_uuid
from shared.domain.entities.lead import Lead

router = APIRouter(tags=["admin-leads"])


class LeadResponse(BaseModel):
    id: UUID
    hubla_subscription_id: str
    payer_phone: str
    payer_name: str
    payer_email: str
    payer_document: str | None
    hubla_product_id: str
    product_name: str
    offer_name: str | None
    amount_total_cents: int | None
    payment_method: str | None
    subscription_status: str
    utm_source: str | None
    utm_campaign: str | None
    first_seen_at: datetime
    activated_at: datetime | None
    last_event_at: datetime
    last_event_type: str
    chatnexo_conversation_url: str | None = None


class LeadListResponse(BaseModel):
    items: list[LeadResponse]
    total: int
    page: int
    page_size: int


class HublaEventResponse(BaseModel):
    id: UUID
    event_type: str
    received_at: datetime
    payer_phone: str
    product_name: str


class OnboardingStepDetailResponse(BaseModel):
    id: UUID
    position: int
    template_name: str | None
    message_text: str | None
    status: str  # "sent" | "pending" | "failed" | "cancelled"
    delay_from_previous_minutes: int
    scheduled_for: datetime | None
    sent_at: datetime | None
    failure_reason: str | None
    rendered_preview: str | None


class OnboardingEnrollmentDetailResponse(BaseModel):
    id: UUID
    flow_id: UUID | None
    flow_name: str
    product_name: str
    trigger_event_type: str
    enrolled_at: datetime
    steps: list[OnboardingStepDetailResponse]


class LeadDetailResponse(LeadResponse):
    events: list[HublaEventResponse]
    enrollments: list[OnboardingEnrollmentDetailResponse]


def _to_response(m: Lead) -> LeadResponse:
    return LeadResponse(
        id=m.id,
        hubla_subscription_id=m.hubla_subscription_id,
        payer_phone=m.payer_phone,
        payer_name=m.payer_name,
        payer_email=m.payer_email,
        payer_document=m.payer_document,
        hubla_product_id=m.hubla_product_id,
        product_name=m.product_name,
        offer_name=m.offer_name,
        amount_total_cents=m.amount_total_cents,
        payment_method=m.payment_method,
        subscription_status=m.subscription_status,
        utm_source=m.utm_source,
        utm_campaign=m.utm_campaign,
        first_seen_at=m.first_seen_at,
        activated_at=m.activated_at,
        last_event_at=m.last_event_at,
        last_event_type=m.last_event_type,
        chatnexo_conversation_url=m.chatnexo_conversation_url,
    )


@router.get("/leads", response_model=LeadListResponse)
async def list_leads(
    product_id: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    utm_source: str | None = Query(default=None),
    date_from: datetime | None = Query(default=None),  # noqa: B008
    date_to: datetime | None = Query(default=None),  # noqa: B008
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
    auth: AdminAuth = Depends(require_admin),  # noqa: B008
) -> LeadListResponse:
    async with session_scope() as session:
        account_uuid = await get_default_account_uuid(session)
        repo = SqlLeadRepository(session=session)
        items, total = await repo.paginate(
            account_uuid,
            product_id=product_id,
            status=status_filter,
            utm_source=utm_source,
            date_from=date_from,
            date_to=date_to,
            page=page,
            page_size=page_size,
        )
    return LeadListResponse(
        items=[_to_response(m) for m in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/leads/export")
async def export_leads(
    product_id: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    utm_source: str | None = Query(default=None),
    date_from: datetime | None = Query(default=None),  # noqa: B008
    date_to: datetime | None = Query(default=None),  # noqa: B008
    auth: AdminAuth = Depends(require_admin),  # noqa: B008
) -> StreamingResponse:
    async with session_scope() as session:
        account_uuid = await get_default_account_uuid(session)
        repo = SqlLeadRepository(session=session)
        items, _ = await repo.paginate(
            account_uuid,
            product_id=product_id,
            status=status_filter,
            utm_source=utm_source,
            date_from=date_from,
            date_to=date_to,
            page=1,
            page_size=10_000,
        )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "nome",
            "telefone",
            "email",
            "cpf",
            "produto",
            "oferta",
            "valor_total_r$",
            "metodo_pagamento",
            "status",
            "utm_source",
            "utm_campaign",
            "utm_medium",
            "utm_content",
            "utm_term",
            "data_primeiro_evento",
            "data_ativacao",
        ]
    )
    for m in items:
        valor = (
            f"{(m.amount_total_cents or 0) / 100:.2f}".replace(".", ",")
            if m.amount_total_cents is not None
            else ""
        )
        writer.writerow(
            [
                m.payer_name,
                m.payer_phone,
                m.payer_email,
                m.payer_document or "",
                m.product_name,
                m.offer_name or "",
                valor,
                m.payment_method or "",
                m.subscription_status,
                m.utm_source or "",
                m.utm_campaign or "",
                m.utm_medium or "",
                m.utm_content or "",
                m.utm_term or "",
                m.first_seen_at.strftime("%d/%m/%Y %H:%M") if m.first_seen_at else "",
                m.activated_at.strftime("%d/%m/%Y %H:%M") if m.activated_at else "",
            ]
        )

    csv_data = "﻿" + output.getvalue()
    date_str = datetime.now().strftime("%Y%m%d")
    return StreamingResponse(
        iter([csv_data]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="leads-{date_str}.csv"'},
    )


@router.get("/leads/utm-sources/suggest", response_model=list[str])
async def suggest_utm_sources(
    q: str | None = Query(default=None),
    auth: AdminAuth = Depends(require_admin),  # noqa: B008
) -> list[str]:
    async with session_scope() as session:
        account_uuid = await get_default_account_uuid(session)
        repo = SqlLeadRepository(session=session)
        return await repo.suggest_utm_sources(account_uuid, q=q)


@router.get("/leads/{lead_id}", response_model=LeadDetailResponse)
async def get_lead(
    lead_id: UUID,
    auth: AdminAuth = Depends(require_admin),  # noqa: B008
) -> LeadDetailResponse:
    async with session_scope() as session:
        account_uuid = await get_default_account_uuid(session)
        repo = SqlLeadRepository(session=session)
        m = await repo.find_by_id(lead_id, account_uuid)
        if m is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="lead not found")
        events = await repo.get_events(account_uuid, m.hubla_subscription_id)
        enrollments = await repo.get_enrollments(account_uuid, m.hubla_subscription_id)

    return LeadDetailResponse(
        **_to_response(m).model_dump(),
        events=[
            HublaEventResponse(
                id=e.id,
                event_type=e.event_type,
                received_at=e.received_at,
                payer_phone=e.payer_phone,
                product_name=e.product_name,
            )
            for e in events
        ],
        enrollments=[
            OnboardingEnrollmentDetailResponse(
                id=e["id"],
                flow_id=e["flow_id"],
                flow_name=e["flow_name"],
                product_name=e["product_name"],
                trigger_event_type=e["trigger_event_type"],
                enrolled_at=e["enrolled_at"],
                steps=[OnboardingStepDetailResponse(**s) for s in e["steps"]],
            )
            for e in enrollments
        ],
    )
