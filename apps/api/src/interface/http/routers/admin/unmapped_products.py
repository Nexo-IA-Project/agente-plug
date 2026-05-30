"""Router admin de "Pendências" — produtos Hubla não reconhecidos (Task 7).

Endpoints:
  GET  /admin/unmapped-products          → lista grupos pendentes
  POST /admin/unmapped-products/resolve  → associa hubla_product_id a um produto (alias)
  POST /admin/unmapped-products/reprocess→ re-enfileira os hubla_events afetados
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from interface.http.deps.admin_auth import AdminAuth
from interface.http.deps.permissions import require_permission
from shared.adapters.db.repositories.lead_repo import SqlLeadRepository
from shared.adapters.db.repositories.product_repo import SqlProductRepository
from shared.adapters.db.session import session_scope
from shared.application.use_cases.admin import unmapped_products as uc
from shared.config.single_tenant import get_default_account_uuid

router = APIRouter(tags=["admin-unmapped-products"])


class UnmappedProductResponse(BaseModel):
    hubla_product_id: str
    product_name: str
    affected_leads: int
    first_seen: datetime | None
    last_seen: datetime | None


class ResolveRequest(BaseModel):
    hubla_product_id: str
    product_id: UUID


class ResolveResponse(BaseModel):
    affected_leads: int


class ReprocessRequest(BaseModel):
    hubla_product_id: str
    schedule_mode: Literal["from_now", "original"] = "from_now"


class ReprocessResponse(BaseModel):
    enqueued: int


@router.get("/unmapped-products", response_model=list[UnmappedProductResponse])
async def list_unmapped_products(
    auth: AdminAuth = Depends(require_permission("onboarding.view")),
) -> list[UnmappedProductResponse]:
    async with session_scope() as session:
        account_uuid = await get_default_account_uuid(session)
        lead_repo = SqlLeadRepository(session=session)
        rows = await uc.list_unmapped(account_uuid, lead_repo)
    return [UnmappedProductResponse(**row) for row in rows]


@router.post("/unmapped-products/resolve", response_model=ResolveResponse)
async def resolve_unmapped_product(
    body: ResolveRequest,
    auth: AdminAuth = Depends(require_permission("onboarding.resolve_unmapped")),
) -> ResolveResponse:
    async with session_scope() as session:
        account_uuid = await get_default_account_uuid(session)
        product_repo = SqlProductRepository(session=session)
        lead_repo = SqlLeadRepository(session=session)
        result = await uc.resolve(
            account_id=account_uuid,
            hubla_product_id=body.hubla_product_id,
            product_id=body.product_id,
            product_repo=product_repo,
            lead_repo=lead_repo,
        )
    return ResolveResponse(**result)


@router.post("/unmapped-products/reprocess", response_model=ReprocessResponse)
async def reprocess_unmapped_product(
    body: ReprocessRequest,
    auth: AdminAuth = Depends(require_permission("onboarding.resolve_unmapped")),
) -> ReprocessResponse:
    async with session_scope() as session:
        account_uuid = await get_default_account_uuid(session)
        result = await uc.reprocess(
            account_id=account_uuid,
            hubla_product_id=body.hubla_product_id,
            schedule_mode=body.schedule_mode,
            session=session,
        )
    return ReprocessResponse(**result)
