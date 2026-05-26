"""Endpoints de relatório de enrollments para o painel admin.

- ``GET /admin/onboarding/enrollments`` — lista paginada com filtros.
- ``GET /admin/onboarding/enrollments/{id}/steps`` — steps de um enrollment com
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
from shared.adapters.db.repositories.onboarding_enrollment_repo import (
    OnboardingEnrollmentRepository,
)
from shared.adapters.db.session import session_scope
from shared.domain.entities.onboarding import EnrollmentStatus

router = APIRouter(tags=["admin-onboarding-reports"])


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


@router.get("/onboarding/enrollments", response_model=EnrollmentListResponse)
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
        repo = OnboardingEnrollmentRepository(session=session)
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
    "/onboarding/enrollments/{enrollment_id}/steps",
    response_model=list[EnrollmentStepItem],
)
async def list_enrollment_steps(
    enrollment_id: UUID,
    auth: AdminAuth = Depends(require_admin),  # noqa: B008
) -> list[EnrollmentStepItem]:
    async with session_scope() as session:
        account_uuid = await _get_account_uuid(session, auth)
        repo = OnboardingEnrollmentRepository(session=session)
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


class DispatchNowResponse(BaseModel):
    status: str  # "sent" | "failed"
    failure_reason: str | None
    sent_at: str | None


@router.post(
    "/onboarding/enrollments/{enrollment_id}/steps/{step_id}/dispatch-now",
    response_model=DispatchNowResponse,
)
async def dispatch_step_now(
    enrollment_id: UUID,
    step_id: UUID,
    auth: AdminAuth = Depends(require_admin),  # noqa: B008
) -> DispatchNowResponse:
    """Força o disparo imediato de um step pending ou failed.

    Pipeline:
      1. Resolve account + carrega o enrollment_step
      2. Valida que o step pertence ao enrollment passado (defense in depth)
      3. Reset do status para PENDING + clear de failure_reason (permite retry de failed)
      4. Cancela o ScheduledJob futuro (se houver) — evita disparo duplicado
      5. Executa DispatchOnboardingStep síncrono
      6. Retorna status final (sent | failed)
    """
    from cryptography.fernet import Fernet
    from sqlalchemy import update

    from agent.history import ConversationHistory
    from shared.adapters.chatnexo.client import ChatNexoClient
    from shared.adapters.db.models import (
        OnboardingEnrollmentStepModel,
        ScheduledJobModel,
    )
    from shared.adapters.db.repositories.account_config_repo import AccountConfigRepository
    from shared.adapters.db.repositories.contact import ContactRepository
    from shared.adapters.db.repositories.meta_template_repo import MetaTemplateRepository
    from shared.application.use_cases.onboarding.dispatch_onboarding_step import (
        DispatchOnboardingStep,
    )
    from shared.config.settings import get_settings
    from shared.domain.entities.onboarding import EnrollmentStepStatus

    async with session_scope() as session:
        account_uuid = await _get_account_uuid(session, auth)

        # 1+2. Resolve step e valida ownership (enrollment, account)
        repo = OnboardingEnrollmentRepository(session=session)
        step = await repo.find_step_by_id(step_id)
        if step is None or step.enrollment_id != enrollment_id:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="step não encontrado",
            )
        enrollment = await repo.find_enrollment_by_id(enrollment_id)
        if enrollment is None or enrollment.account_id != account_uuid:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="enrollment não encontrado",
            )

        # 3. Reset do status pra permitir o dispatch executar (failed → pending)
        await session.execute(
            update(OnboardingEnrollmentStepModel)
            .where(OnboardingEnrollmentStepModel.id == step_id)
            .values(status="pending", failure_reason=None)
        )

        # 4. Cancela job futuro (se houver) — evita race com o scheduler
        if step.scheduled_job_id is not None:
            await session.execute(
                update(ScheduledJobModel)
                .where(
                    ScheduledJobModel.id == step.scheduled_job_id,
                    ScheduledJobModel.status == "pending",
                )
                .values(status="cancelled")
            )

        await session.flush()

        # 5. Despacha síncrono
        settings_obj = get_settings()
        fernet = Fernet(settings_obj.integration_credentials_key.encode())
        config_repo = AccountConfigRepository(session=session, fernet=fernet)
        config = await config_repo.get(account_id=1)
        chatnexo = ChatNexoClient.from_account_config(config)
        dispatch = DispatchOnboardingStep(
            enrollment_repo=repo,
            contact_repo=ContactRepository(session=session),
            chatnexo=chatnexo,
            conversation_history=ConversationHistory(session=session),
            meta_template_repo=MetaTemplateRepository(session=session),
        )
        result = await dispatch.execute(
            enrollment_step_id=step_id,
            account_id=account_uuid,
            conversation_id=str(enrollment.conversation_id),
            contact_phone=enrollment.contact_phone,
        )

        # 6. Recarrega step pra pegar sent_at atualizado
        refreshed = await repo.find_step_by_id(step_id)
        sent_at_iso = refreshed.sent_at.isoformat() if refreshed and refreshed.sent_at else None

    return DispatchNowResponse(
        status="sent" if result.status == EnrollmentStepStatus.SENT else "failed",
        failure_reason=result.failure_reason,
        sent_at=sent_at_iso,
    )
