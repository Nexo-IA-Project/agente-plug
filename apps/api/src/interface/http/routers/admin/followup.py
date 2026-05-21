from __future__ import annotations

import uuid as _uuid_module
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from interface.http.deps.admin_auth import AdminAuth, require_admin
from interface.http.schemas.followup import (
    CourseSummary,
    CreateFlowRequest,
    CreateStepRequest,
    FollowupFlowResponse,
    FollowupStepResponse,
    ReorderStepsRequest,
    StepVariableBindingDto,
    UpdateFlowRequest,
    UpdateStepRequest,
)
from shared.adapters.db.models import AccountModel
from shared.adapters.db.queue import PostgresJobQueue
from shared.adapters.db.repositories.course_repo import SqlCourseRepository
from shared.adapters.db.repositories.followup_flow_repo import FollowupFlowRepository
from shared.adapters.db.session import get_sessionmaker, session_scope

router = APIRouter(tags=["admin-followup"])


async def _get_account_uuid(session) -> _uuid_module.UUID:
    result = await session.execute(select(AccountModel.id).limit(1))
    return result.scalar_one()


async def _enqueue_resync(flow_id: UUID, account_id: _uuid_module.UUID) -> None:
    """Enfileira job de resync após mutação de step do flow.

    Usa sessionmaker próprio do PostgresJobQueue (commit independente).
    Deve ser chamado APÓS o session_scope da mutação ser commitado.
    """
    queue = PostgresJobQueue(sessionmaker=get_sessionmaker())
    await queue.enqueue(
        {
            "kind": "resync_flow",
            "payload": {
                "flow_id": str(flow_id),
                "account_id": str(account_id),
            },
        }
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


def _bindings_to_dict(
    bindings: dict[str, StepVariableBindingDto] | None,
) -> dict:
    if not bindings:
        return {}
    return {k: v.model_dump(exclude_none=True) for k, v in bindings.items()}


@router.get("/followup/flows", response_model=list[FollowupFlowResponse])
async def list_flows(
    auth: AdminAuth = Depends(require_admin),  # noqa: B008
) -> list[FollowupFlowResponse]:
    async with session_scope() as session:
        account_uuid = await _get_account_uuid(session)
        flow_repo = FollowupFlowRepository(session=session)
        course_repo = SqlCourseRepository(session=session)
        flows = await flow_repo.list_flows(account_id=account_uuid)
        out: list[FollowupFlowResponse] = []
        for f in flows:
            course = await course_repo.find_by_id(f.course_id)
            steps = await flow_repo.get_steps(f.id)
            if course is None:
                # FK garante que existe; defensivo
                continue
            out.append(
                FollowupFlowResponse(
                    id=f.id,
                    name=f.name,
                    is_active=f.is_active,
                    course=CourseSummary(id=course.id, name=course.name, hubla_id=course.hubla_id),
                    steps_count=len(steps),
                    created_at=f.created_at,
                    updated_at=f.updated_at,
                )
            )
    return out


@router.post(
    "/followup/flows",
    response_model=FollowupFlowResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_flow(
    body: CreateFlowRequest,
    auth: AdminAuth = Depends(require_admin),  # noqa: B008
) -> FollowupFlowResponse:
    async with session_scope() as session:
        account_uuid = await _get_account_uuid(session)
        course_repo = SqlCourseRepository(session=session)
        course = await course_repo.find_by_id(body.course_id)
        if course is None or course.account_id != account_uuid:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="course not found",
            )
        flow_repo = FollowupFlowRepository(session=session)
        flow = await flow_repo.create_flow(
            account_id=account_uuid,
            course_id=body.course_id,
            name=body.name,
            is_active=body.is_active,
        )
    return FollowupFlowResponse(
        id=flow.id,
        name=flow.name,
        is_active=flow.is_active,
        course=CourseSummary(id=course.id, name=course.name, hubla_id=course.hubla_id),
        steps_count=0,
        created_at=flow.created_at,
        updated_at=flow.updated_at,
    )


@router.put("/followup/flows/{flow_id}", response_model=FollowupFlowResponse)
async def update_flow(
    flow_id: UUID,
    body: UpdateFlowRequest,
    auth: AdminAuth = Depends(require_admin),  # noqa: B008
) -> FollowupFlowResponse:
    async with session_scope() as session:
        account_uuid = await _get_account_uuid(session)
        course_repo = SqlCourseRepository(session=session)
        if body.course_id is not None:
            target_course = await course_repo.find_by_id(body.course_id)
            if target_course is None or target_course.account_id != account_uuid:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="course not found",
                )
        flow_repo = FollowupFlowRepository(session=session)
        flow = await flow_repo.update_flow(
            flow_id,
            name=body.name,
            course_id=body.course_id,
            is_active=body.is_active,
        )
        if flow is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flow não encontrado")
        course = await course_repo.find_by_id(flow.course_id)
        steps = await flow_repo.get_steps(flow.id)
        if course is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="course not found")
    return FollowupFlowResponse(
        id=flow.id,
        name=flow.name,
        is_active=flow.is_active,
        course=CourseSummary(id=course.id, name=course.name, hubla_id=course.hubla_id),
        steps_count=len(steps),
        created_at=flow.created_at,
        updated_at=flow.updated_at,
    )


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
        account_uuid = await _get_account_uuid(session)
        repo = FollowupFlowRepository(session=session)
        existing = await repo.get_steps(flow_id)
        position = body.position if body.position is not None else len(existing)
        step = await repo.create_step(
            flow_id=flow_id,
            position=position,
            delay_from_purchase_hours=body.delay_from_purchase_hours,
            meta_template_name=body.meta_template_name,
            template_variables=_bindings_to_dict(body.template_variables),
            message_text=body.message_text,
        )
    await _enqueue_resync(flow_id, account_uuid)
    return _step_to_resp(step)


@router.put("/followup/flows/{flow_id}/steps/{step_id}", response_model=FollowupStepResponse)
async def update_step(
    flow_id: UUID,
    step_id: UUID,
    body: UpdateStepRequest,
    auth: AdminAuth = Depends(require_admin),  # noqa: B008
) -> FollowupStepResponse:
    async with session_scope() as session:
        account_uuid = await _get_account_uuid(session)
        repo = FollowupFlowRepository(session=session)
        template_vars = (
            _bindings_to_dict(body.template_variables)
            if body.template_variables is not None
            else None
        )
        step = await repo.update_step(
            step_id,
            position=body.position,
            delay_from_purchase_hours=body.delay_from_purchase_hours,
            meta_template_name=body.meta_template_name,
            template_variables=template_vars,
            message_text=body.message_text,
            clear_template=body.message_text is not None and body.meta_template_name is None,
            clear_message_text=body.meta_template_name is not None and body.message_text is None,
        )
    if step is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Step não encontrado")
    await _enqueue_resync(flow_id, account_uuid)
    return _step_to_resp(step)


@router.delete("/followup/flows/{flow_id}/steps/{step_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_step(
    flow_id: UUID,
    step_id: UUID,
    auth: AdminAuth = Depends(require_admin),  # noqa: B008
) -> None:
    async with session_scope() as session:
        account_uuid = await _get_account_uuid(session)
        repo = FollowupFlowRepository(session=session)
        deleted = await repo.delete_step(step_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Step não encontrado")
    await _enqueue_resync(flow_id, account_uuid)


@router.patch("/followup/flows/{flow_id}/steps/reorder", status_code=status.HTTP_204_NO_CONTENT)
async def reorder_steps(
    flow_id: UUID,
    body: ReorderStepsRequest,
    auth: AdminAuth = Depends(require_admin),  # noqa: B008
) -> None:
    async with session_scope() as session:
        account_uuid = await _get_account_uuid(session)
        repo = FollowupFlowRepository(session=session)
        for item in body.steps:
            await repo.update_step(item.id, position=item.position)
    await _enqueue_resync(flow_id, account_uuid)
