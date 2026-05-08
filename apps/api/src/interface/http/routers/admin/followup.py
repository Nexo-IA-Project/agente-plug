from __future__ import annotations

import uuid as _uuid_module
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from interface.http.deps.admin_auth import AdminAuth, require_admin
from interface.http.schemas.followup import (
    CreateFlowRequest,
    CreateStepRequest,
    FollowupFlowResponse,
    FollowupStepResponse,
    ReorderStepsRequest,
    UpdateFlowRequest,
    UpdateStepRequest,
)
from shared.adapters.db.models import AccountModel
from shared.adapters.db.repositories.followup_flow_repo import FollowupFlowRepository
from shared.adapters.db.session import session_scope

router = APIRouter(tags=["admin-followup"])


async def _get_account_uuid(session) -> _uuid_module.UUID:
    result = await session.execute(select(AccountModel.id).limit(1))
    return result.scalar_one()


def _flow_to_resp(f) -> FollowupFlowResponse:
    return FollowupFlowResponse(
        id=f.id,
        account_id=f.account_id,
        name=f.name,
        product_tags=f.product_tags,
        is_active=f.is_active,
        created_at=f.created_at,
        updated_at=f.updated_at,
    )


def _step_to_resp(s) -> FollowupStepResponse:
    return FollowupStepResponse(
        id=s.id,
        flow_id=s.flow_id,
        position=s.position,
        delay_from_purchase_hours=s.delay_from_purchase_hours,
        meta_template_name=s.meta_template_name,
        template_variables=s.template_variables,
        message_text=s.message_text,
        created_at=s.created_at,
    )


@router.get("/followup/flows", response_model=list[FollowupFlowResponse])
async def list_flows(auth: AdminAuth = Depends(require_admin)) -> list[FollowupFlowResponse]:  # noqa: B008
    async with session_scope() as session:
        account_uuid = await _get_account_uuid(session)
        repo = FollowupFlowRepository(session=session)
        flows = await repo.list_flows(account_id=account_uuid)
    return [_flow_to_resp(f) for f in flows]


@router.post(
    "/followup/flows", response_model=FollowupFlowResponse, status_code=status.HTTP_201_CREATED
)
async def create_flow(
    body: CreateFlowRequest,
    auth: AdminAuth = Depends(require_admin),  # noqa: B008
) -> FollowupFlowResponse:
    async with session_scope() as session:
        account_uuid = await _get_account_uuid(session)
        repo = FollowupFlowRepository(session=session)
        flow = await repo.create_flow(
            account_id=account_uuid,
            name=body.name,
            product_tags=body.product_tags,
        )
    return _flow_to_resp(flow)


@router.put("/followup/flows/{flow_id}", response_model=FollowupFlowResponse)
async def update_flow(
    flow_id: UUID,
    body: UpdateFlowRequest,
    auth: AdminAuth = Depends(require_admin),  # noqa: B008
) -> FollowupFlowResponse:
    async with session_scope() as session:
        repo = FollowupFlowRepository(session=session)
        flow = await repo.update_flow(
            flow_id,
            name=body.name,
            product_tags=body.product_tags,
            is_active=body.is_active,
        )
    if flow is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flow não encontrado")
    return _flow_to_resp(flow)


@router.delete("/followup/flows/{flow_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_flow(
    flow_id: UUID,
    auth: AdminAuth = Depends(require_admin),  # noqa: B008
) -> None:
    async with session_scope() as session:
        repo = FollowupFlowRepository(session=session)
        deleted = await repo.delete_flow(flow_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flow não encontrado")


@router.get("/followup/flows/{flow_id}/steps", response_model=list[FollowupStepResponse])
async def list_steps(
    flow_id: UUID,
    auth: AdminAuth = Depends(require_admin),  # noqa: B008
) -> list[FollowupStepResponse]:
    async with session_scope() as session:
        repo = FollowupFlowRepository(session=session)
        steps = await repo.get_steps(flow_id)
    return [_step_to_resp(s) for s in steps]


@router.post(
    "/followup/flows/{flow_id}/steps",
    response_model=FollowupStepResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_step(
    flow_id: UUID,
    body: CreateStepRequest,
    auth: AdminAuth = Depends(require_admin),  # noqa: B008
) -> FollowupStepResponse:
    async with session_scope() as session:
        repo = FollowupFlowRepository(session=session)
        step = await repo.create_step(
            flow_id=flow_id,
            position=body.position,
            delay_from_purchase_hours=body.delay_from_purchase_hours,
            meta_template_name=body.meta_template_name,
            template_variables=body.template_variables,
            message_text=body.message_text,
        )
    return _step_to_resp(step)


@router.put("/followup/flows/{flow_id}/steps/{step_id}", response_model=FollowupStepResponse)
async def update_step(
    flow_id: UUID,
    step_id: UUID,
    body: UpdateStepRequest,
    auth: AdminAuth = Depends(require_admin),  # noqa: B008
) -> FollowupStepResponse:
    async with session_scope() as session:
        repo = FollowupFlowRepository(session=session)
        step = await repo.update_step(
            step_id,
            position=body.position,
            delay_from_purchase_hours=body.delay_from_purchase_hours,
            meta_template_name=body.meta_template_name,
            template_variables=body.template_variables,
            message_text=body.message_text,
            clear_template=body.message_text is not None and body.meta_template_name is None,
            clear_message_text=body.meta_template_name is not None and body.message_text is None,
        )
    if step is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Step não encontrado")
    return _step_to_resp(step)


@router.delete("/followup/flows/{flow_id}/steps/{step_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_step(
    flow_id: UUID,
    step_id: UUID,
    auth: AdminAuth = Depends(require_admin),  # noqa: B008
) -> None:
    async with session_scope() as session:
        repo = FollowupFlowRepository(session=session)
        deleted = await repo.delete_step(step_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Step não encontrado")


@router.patch("/followup/flows/{flow_id}/steps/reorder", status_code=status.HTTP_204_NO_CONTENT)
async def reorder_steps(
    flow_id: UUID,
    body: ReorderStepsRequest,
    auth: AdminAuth = Depends(require_admin),  # noqa: B008
) -> None:
    async with session_scope() as session:
        repo = FollowupFlowRepository(session=session)
        for item in body.steps:
            await repo.update_step(item.id, position=item.position)
