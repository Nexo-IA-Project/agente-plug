from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import structlog

from shared.domain.entities.followup import EnrollmentStatus, EnrollmentStepStatus

log = structlog.get_logger(__name__)


class DispatchFollowupStep:
    def __init__(self, *, enrollment_repo: Any, chatnexo: Any, conversation_history: Any) -> None:
        self._enrollment_repo = enrollment_repo
        self._chatnexo = chatnexo
        self._history = conversation_history

    async def execute(
        self,
        *,
        enrollment_step_id: UUID,
        account_id: UUID,
        conversation_id: str,
        contact_phone: str,
    ) -> str:
        step = await self._enrollment_repo.find_step_by_id(enrollment_step_id)
        if step is None:
            log.warning("followup_step_not_found", step_id=str(enrollment_step_id))
            return "ERRO: step não encontrado"

        if step.status != EnrollmentStepStatus.PENDING:
            log.info("followup_step_skipped", step_id=str(step.id), status=step.status)
            return "IGNORADO"

        if step.message_text:
            await self._chatnexo.send_message(
                account_id=str(account_id),
                conversation_id=str(conversation_id),
                text=step.message_text,
            )
            dispatch_label = f"texto_livre: {step.message_text[:40]}"
        else:
            header_link = getattr(step, "media_url", None) or None
            header_kind = getattr(step, "media_kind", None) or None
            await self._chatnexo.send_template(
                account_id=str(account_id),
                conversation_id=str(conversation_id),
                template_name=step.meta_template_name,
                language=getattr(step, "language", None) or None,
                variables=step.template_variables,
                header_link=header_link,
                header_kind=header_kind,
            )
            dispatch_label = f"template={step.meta_template_name}"

        thread_id = f"{account_id}:{contact_phone}"
        messages = await self._history.load(thread_id=thread_id)
        messages.append(
            {
                "role": "assistant",
                "content": f"[Mensagem automática de follow-up enviada: {dispatch_label}]",
            }
        )
        await self._history.save(thread_id=thread_id, messages=messages)

        step.status = EnrollmentStepStatus.SENT
        step.sent_at = datetime.now(UTC)
        await self._enrollment_repo.update_step(step)

        if await self._enrollment_repo.all_steps_sent(step.enrollment_id):
            await self._enrollment_repo.update_enrollment_status(
                step.enrollment_id, EnrollmentStatus.COMPLETED
            )

        log.info(
            "followup_step_dispatched",
            step_id=str(step.id),
            template=step.meta_template_name,
            has_text=bool(step.message_text),
        )
        return "SENT"
