from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError

from interface.http.deps.admin_auth import AdminAuth, require_admin
from shared.adapters.db.repositories.product_repo import SqlProductRepository
from shared.adapters.db.session import session_scope
from shared.config.single_tenant import get_default_account_uuid

router = APIRouter(tags=["admin-products"])


class CreateProductRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    hubla_id: str = Field(min_length=1, max_length=200)
    is_active: bool = True


class UpdateProductRequest(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    hubla_id: str | None = Field(default=None, max_length=200)
    is_active: bool | None = None


class ProductResponse(BaseModel):
    id: UUID
    name: str
    hubla_id: str
    is_active: bool
    flow_count: int
    created_at: datetime
    updated_at: datetime


@router.get("/products", response_model=list[ProductResponse])
async def list_products(
    auth: AdminAuth = Depends(require_admin),  # noqa: B008
) -> list[ProductResponse]:
    async with session_scope() as session:
        account_uuid = await get_default_account_uuid(session)
        repo = SqlProductRepository(session=session)
        products = await repo.list_by_account(account_uuid)
        items: list[ProductResponse] = []
        for p in products:
            items.append(
                ProductResponse(
                    id=p.id,
                    name=p.name,
                    hubla_id=p.hubla_id,
                    is_active=p.is_active,
                    flow_count=await repo.count_flows(p.id),
                    created_at=p.created_at,
                    updated_at=p.updated_at,
                )
            )
    return items


@router.post("/products", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    body: CreateProductRequest,
    auth: AdminAuth = Depends(require_admin),  # noqa: B008
) -> ProductResponse:
    async with session_scope() as session:
        account_uuid = await get_default_account_uuid(session)
        repo = SqlProductRepository(session=session)
        try:
            p = await repo.create(
                account_id=account_uuid,
                name=body.name,
                hubla_id=body.hubla_id,
                is_active=body.is_active,
            )
        except IntegrityError as exc:
            await session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="product with hubla_id already exists",
            ) from exc
    return ProductResponse(
        id=p.id,
        name=p.name,
        hubla_id=p.hubla_id,
        is_active=p.is_active,
        flow_count=0,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


@router.put("/products/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: UUID,
    body: UpdateProductRequest,
    auth: AdminAuth = Depends(require_admin),  # noqa: B008
) -> ProductResponse:
    async with session_scope() as session:
        repo = SqlProductRepository(session=session)
        try:
            p = await repo.update(
                product_id,
                name=body.name,
                hubla_id=body.hubla_id,
                is_active=body.is_active,
            )
        except IntegrityError as exc:
            await session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="product with hubla_id already exists",
            ) from exc
        if p is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="product not found")
        flow_count = await repo.count_flows(p.id)
    return ProductResponse(
        id=p.id,
        name=p.name,
        hubla_id=p.hubla_id,
        is_active=p.is_active,
        flow_count=flow_count,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


@router.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: UUID,
    auth: AdminAuth = Depends(require_admin),  # noqa: B008
) -> None:
    async with session_scope() as session:
        repo = SqlProductRepository(session=session)
        existing = await repo.find_by_id(product_id)
        if existing is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="product not found")
        flow_count = await repo.count_flows(product_id)
        if flow_count > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"product has {flow_count} flow(s) linked",
            )
        await repo.delete(product_id)
