from __future__ import annotations

import structlog

from shared.application.lifecycle_handler import LifecycleHandler
from shared.domain.entities.scheduled_job import JobType

log = structlog.get_logger(__name__)


def _get_lifecycle_handler() -> LifecycleHandler:
    raise NotImplementedError("_get_lifecycle_handler: configure DI em main.py")


def _get_dispatch_followup_step_handler():
    raise NotImplementedError("_get_dispatch_followup_step_handler: configure DI em worker.py")


async def handle_scheduled(payload: dict) -> None:
    job_type: str = payload["job_type"]
    account_id: str = payload["account_id"]
    phone: str = payload.get("phone", "")
    conversation_id: str = payload["conversation_id"]

    if job_type == "IDLE_PING":
        lifecycle = _get_lifecycle_handler()
        await lifecycle.send_ping(
            account_id=account_id, phone=phone, conversation_id=conversation_id
        )
    elif job_type == "IDLE_CLOSE":
        lifecycle = _get_lifecycle_handler()
        await lifecycle.send_close(
            account_id=account_id, phone=phone, conversation_id=conversation_id
        )
    elif job_type in (JobType.FOLLOWUP_STEP.value, "onboarding_step"):
        from uuid import UUID as _UUID

        from cryptography.fernet import Fernet

        from agent.history import ConversationHistory
        from shared.adapters.agent_selection.random_selection import RandomAgentSelection
        from shared.adapters.chatnexo.agent_picker import build_chatnexo_client
        from shared.adapters.db.repositories.account_config_repo import AccountConfigRepository
        from shared.adapters.db.repositories.contact import ContactRepository
        from shared.adapters.db.repositories.conversation import ConversationRepository
        from shared.adapters.db.repositories.meta_template_repo import MetaTemplateRepository
        from shared.adapters.db.repositories.onboarding_enrollment_repo import (
            OnboardingEnrollmentRepository,
        )
        from shared.adapters.db.repositories.onboarding_flow_repo import (
            OnboardingFlowRepository,
        )
        from shared.adapters.db.session import session_scope
        from shared.adapters.redis.leads_pubsub import LeadsPubSub
        from shared.application.use_cases.onboarding.dispatch_onboarding_step import (
            DispatchOnboardingStep,
        )
        from shared.config.settings import get_settings
        from shared.config.single_tenant import get_default_account_uuid
        from shared.domain.entities.onboarding import EnrollmentStepStatus

        settings_obj = get_settings()
        fernet = Fernet(settings_obj.integration_credentials_key.encode())
        async with session_scope() as session:
            config_repo = AccountConfigRepository(session=session, fernet=fernet)
            account_uuid = await get_default_account_uuid(session)
            config = await config_repo.get(account_id=account_uuid)
            agents = config.integration.chatnexo_agents
            base_url = config.integration.chatnexo_base_url
            fallback_key = config.integration.chatnexo_api_key
            chatnexo, chosen_agent_id = build_chatnexo_client(
                base_url=base_url,
                agents=agents,
                strategy=RandomAgentSelection(),
                fallback_api_key=fallback_key,
            )
            dispatch = DispatchOnboardingStep(
                enrollment_repo=OnboardingEnrollmentRepository(session=session),
                contact_repo=ContactRepository(session=session),
                chatnexo=chatnexo,
                conversation_history=ConversationHistory(session=session),
                meta_template_repo=MetaTemplateRepository(session=session),
                flow_repo=OnboardingFlowRepository(session=session),
                leads_pubsub=LeadsPubSub(),
                session=session,
            )
            result = await dispatch.execute(
                enrollment_step_id=_UUID(payload["enrollment_step_id"]),
                account_id=_UUID(payload["account_id"]),
                conversation_id=payload["conversation_id"],
                contact_phone=payload.get("contact_phone", ""),
                chatnexo_account_id=config.integration.chatnexo_account_id,
            )

            # Persistir agente escolhido na conversa para a IA travar o atendente
            if chosen_agent_id and result.status == EnrollmentStepStatus.SENT:
                conv_repo = ConversationRepository(session=session)
                try:
                    chatnexo_conv_id = int(payload["conversation_id"])
                    await conv_repo.set_last_onboarding_agent_id(
                        account_id=account_uuid,
                        chatnexo_conversation_id=chatnexo_conv_id,
                        agent_id=chosen_agent_id,
                    )
                except (ValueError, TypeError):
                    pass

            if result.status == EnrollmentStepStatus.FAILED:
                # Falha de envio é registrada no próprio step com failure_reason.
                # Job termina como sucesso (do ponto de vista da fila) — não vai para DLQ.
                log.warning(
                    "followup_step_dispatch_failed",
                    step_id=payload["enrollment_step_id"],
                    reason=result.failure_reason,
                )
                # NÃO re-raise: o estado fica no step
    else:
        log.warning("unknown_job_type", job_type=job_type)
