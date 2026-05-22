from __future__ import annotations

import uuid as _uuid_module
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from interface.http.deps.admin_auth import AdminAuth, require_admin
from interface.http.schemas.followup import (
    CourseSummary,
    CreateFlowRequest,
    CreateStepRequest,
    FollowupFlowResponse,
    FollowupFlowStats,
    FollowupStepResponse,
    ReorderStepsRequest,
    StepVariableBindingDto,
    UpdateFlowRequest,
    UpdateStepRequest,
)
from shared.adapters.db.models import AccountModel, JobQueueModel
from shared.adapters.db.repositories.followup_flow_repo import FollowupFlowRepository
from shared.adapters.db.repositories.product_repo import SqlProductRepository
from shared.adapters.db.session import session_scope
from shared.domain.value_objects.priority import Priority

router = APIRouter(tags=["admin-followup"])


async def _get_account_uuid(session, auth: AdminAuth) -> _uuid_module.UUID:
    """Resolve ``auth.account_id`` para o UUID do registro em ``accounts``.

    Sistema single-tenant: ``AdminAuth.account_id`` é um ``int`` (atualmente 1)
    e a tabela ``accounts`` usa UUID como PK sem coluna inteira correspondente.
    O lookup retorna o primeiro account encontrado. Quando multi-tenant chegar,
    esta função deve passar a mapear ``auth.account_id`` para o UUID correto.
    """
    _ = auth  # explicitar intenção single-tenant; será usado quando multi-tenant chegar
    result = await session.execute(select(AccountModel.id).limit(1))
    return result.scalar_one()


async def _enqueue_resync_in_session(
    session: AsyncSession,
    *,
    flow_id: UUID,
    account_id: _uuid_module.UUID,
) -> None:
    """Outbox pattern: insere o job de resync na mesma sessão da mutação.

    Garante atomicidade — se o commit do session_scope falhar, o enqueue
    também é revertido; se a mutação commitar, o job estará disponível para o
    worker. Elimina o risco de "mutação commitada mas resync nunca enfileirado"
    que existia ao usar um sessionmaker separado APÓS o session_scope.
    """
    session.add(
        JobQueueModel(
            id=_uuid_module.uuid4(),
            kind="resync_flow",
            payload={
                "flow_id": str(flow_id),
                "account_id": str(account_id),
            },
            attempt=1,
            last_error=None,
            priority=Priority.NORMAL.score,
        )
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
        account_uuid = await _get_account_uuid(session, auth)
        flow_repo = FollowupFlowRepository(session=session)
        product_repo = SqlProductRepository(session=session)
        flows = await flow_repo.list_flows(account_id=account_uuid)
        stats = await flow_repo.stats_by_flows(
            account_id=account_uuid,
            flow_ids=[f.id for f in flows],
        )
        out: list[FollowupFlowResponse] = []
        for f in flows:
            course = await product_repo.find_by_id(f.product_id)
            steps = await flow_repo.get_steps(f.id)
            if course is None:
                # FK garante que existe; defensivo
                continue
            s = stats.get(f.id, {})
            out.append(
                FollowupFlowResponse(
                    id=f.id,
                    name=f.name,
                    is_active=f.is_active,
                    course=CourseSummary(id=course.id, name=course.name, hubla_id=course.hubla_id),
                    steps_count=len(steps),
                    created_at=f.created_at,
                    updated_at=f.updated_at,
                    stats=FollowupFlowStats(
                        enrollments_active=s.get("active", 0),
                        enrollments_completed=s.get("completed", 0),
                    ),
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
        account_uuid = await _get_account_uuid(session, auth)
        product_repo = SqlProductRepository(session=session)
        course = await product_repo.find_by_id(body.product_id)
        if course is None or course.account_id != account_uuid:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="course not found",
            )
        flow_repo = FollowupFlowRepository(session=session)
        flow = await flow_repo.create_flow(
            account_id=account_uuid,
            product_id=body.product_id,
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
        account_uuid = await _get_account_uuid(session, auth)
        product_repo = SqlProductRepository(session=session)
        if body.product_id is not None:
            target_course = await product_repo.find_by_id(body.product_id)
            if target_course is None or target_course.account_id != account_uuid:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="course not found",
                )
        flow_repo = FollowupFlowRepository(session=session)
        flow = await flow_repo.update_flow(
            flow_id,
            name=body.name,
            product_id=body.product_id,
            is_active=body.is_active,
        )
        if flow is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flow não encontrado")
        course = await product_repo.find_by_id(flow.product_id)
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
        account_uuid = await _get_account_uuid(session, auth)
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
        await _enqueue_resync_in_session(session, flow_id=flow_id, account_id=account_uuid)
    return _step_to_resp(step)


@router.put("/followup/flows/{flow_id}/steps/{step_id}", response_model=FollowupStepResponse)
async def update_step(
    flow_id: UUID,
    step_id: UUID,
    body: UpdateStepRequest,
    auth: AdminAuth = Depends(require_admin),  # noqa: B008
) -> FollowupStepResponse:
    async with session_scope() as session:
        account_uuid = await _get_account_uuid(session, auth)
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
        await _enqueue_resync_in_session(session, flow_id=flow_id, account_id=account_uuid)
    return _step_to_resp(step)


@router.delete("/followup/flows/{flow_id}/steps/{step_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_step(
    flow_id: UUID,
    step_id: UUID,
    auth: AdminAuth = Depends(require_admin),  # noqa: B008
) -> None:
    async with session_scope() as session:
        account_uuid = await _get_account_uuid(session, auth)
        repo = FollowupFlowRepository(session=session)
        deleted = await repo.delete_step(step_id)
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Step não encontrado")
        await _enqueue_resync_in_session(session, flow_id=flow_id, account_id=account_uuid)


@router.patch("/followup/flows/{flow_id}/steps/reorder", status_code=status.HTTP_204_NO_CONTENT)
async def reorder_steps(
    flow_id: UUID,
    body: ReorderStepsRequest,
    auth: AdminAuth = Depends(require_admin),  # noqa: B008
) -> None:
    async with session_scope() as session:
        account_uuid = await _get_account_uuid(session, auth)
        repo = FollowupFlowRepository(session=session)
        for item in body.steps:
            await repo.update_step(item.id, position=item.position)
        await _enqueue_resync_in_session(session, flow_id=flow_id, account_id=account_uuid)
