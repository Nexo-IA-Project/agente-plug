from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import structlog

from shared.adapters.db.repositories.meta_template_repo import MetaTemplateRepository
from shared.application.use_cases.onboarding.variable_resolver import (
    ResolutionContext,
    VariableResolver,
)
from shared.domain.entities.onboarding import EnrollmentStatus, EnrollmentStepStatus

log = structlog.get_logger(__name__)


@dataclass(frozen=True)
class DispatchResult:
    """Resultado de DispatchOnboardingStep.execute().

    Atributos:
        status: EnrollmentStepStatus correspondente. SENT no caminho feliz, FAILED
                quando o envio quebra. Para steps já não-PENDING, reflete o status
                atual do step (e label="IGNORADO").
        label: rótulo descritivo (útil para logs/observabilidade).
        failure_reason: motivo (texto humano) quando status=FAILED; None caso contrário.
    """

    status: EnrollmentStepStatus
    label: str
    failure_reason: str | None = None


class DispatchOnboardingStep:
    def __init__(
        self,
        *,
        enrollment_repo: Any,
        contact_repo: Any,
        chatnexo: Any,
        conversation_history: Any,
        meta_template_repo: MetaTemplateRepository,
    ) -> None:
        self._enrollment_repo = enrollment_repo
        self._contact_repo = contact_repo
        self._chatnexo = chatnexo
        self._history = conversation_history
        self._template_repo = meta_template_repo

    async def execute(
        self,
        *,
        enrollment_step_id: UUID,
        account_id: UUID,
        conversation_id: str,
        contact_phone: str,
        chatnexo_account_id: int = 1,
    ) -> DispatchResult:
        step = await self._enrollment_repo.find_step_by_id(enrollment_step_id)
        if step is None:
            log.warning("followup_step_not_found", step_id=str(enrollment_step_id))
            return DispatchResult(
                status=EnrollmentStepStatus.FAILED,
                label="ERRO: step não encontrado",
                failure_reason="step not found",
            )

        if step.status != EnrollmentStepStatus.PENDING:
            log.info("followup_step_skipped", step_id=str(step.id), status=step.status)
            return DispatchResult(status=step.status, label="IGNORADO")

        if step.message_text:
            try:
                await self._chatnexo.send_message(
                    account_id=str(chatnexo_account_id),
                    conversation_id=str(conversation_id),
                    text=step.message_text,
                )
            except Exception as exc:
                reason = str(exc)[:500]
                await self._enrollment_repo.mark_failed(step.id, reason)
                log.warning(
                    "followup_step_send_failed",
                    step_id=str(step.id),
                    kind="message",
                    reason=reason,
                    exc_info=True,
                )
                return DispatchResult(
                    status=EnrollmentStepStatus.FAILED,
                    label="FAILED",
                    failure_reason=reason,
                )
            dispatch_label = f"texto_livre: {step.message_text[:40]}"
        else:
            import re as _re

            header_link: str | None = None
            header_kind: str | None = None
            language: str | None = None
            body_text: str | None = None

            if step.meta_template_name:
                template = await self._template_repo.get_by_name(
                    name=step.meta_template_name,
                    account_id=account_id,
                )
                if template is not None:
                    header_link = template.media_url or None
                    header_kind = template.media_kind.lower() if template.media_kind else None
                    language = template.language or None
                    # Extrai o BODY do template para renderização local — dentro da
                    # janela 24h o ChatNexo envia o `content` como texto livre direto.
                    components = getattr(template, "components", None) or []
                    body_text = next(
                        (c.get("text") for c in components if c.get("type") == "BODY"),
                        None,
                    )
                    log.debug(
                        "followup_step_template_loaded",
                        template_name=step.meta_template_name,
                        has_media=bool(header_link),
                    )
                else:
                    log.warning(
                        "followup_step_template_not_found",
                        template_name=step.meta_template_name,
                        account_id=str(chatnexo_account_id),
                    )

            enrollment = await self._enrollment_repo.find_enrollment_by_id(step.enrollment_id)
            contact_email: str | None = None
            customer_name = ""
            product_name = ""
            phone_value = contact_phone
            if enrollment is not None:
                customer_name = enrollment.customer_name or ""
                product_name = enrollment.product_name or ""
                phone_value = enrollment.contact_phone or contact_phone
                contact = await self._contact_repo.find_by_id(enrollment.contact_id)
                contact_email = getattr(contact, "email", None) if contact else None

            ctx = ResolutionContext(
                customer_name=customer_name,
                product_name=product_name,
                contact_phone=phone_value,
                contact_email=contact_email,
            )
            # Vars do body + vars configuradas no step (união preservando ordem).
            # Cobre 3 casos:
            #   a) Body conhecido (template syncado): pega TODAS as vars do body,
            #      mesmo as não mapeadas (ConventionStrategy resolve via nome).
            #   b) Body desconhecido (template ainda não syncado): usa apenas o
            #      que o user configurou explicitamente.
            #   c) Var configurada que NÃO aparece no body: ainda é enviada
            #      (caller manda no template_params; ChatNexo decide o uso).
            var_names_in_body: list[str] = (
                _re.findall(r"\{\{(\w+)\}\}", body_text) if body_text else []
            )
            configured_vars: dict[str, object] = step.template_variables or {}
            all_var_names: list[str] = list(var_names_in_body)
            for k in configured_vars:
                if k not in all_var_names:
                    all_var_names.append(k)

            resolved_vars = VariableResolver().resolve_template_vars(
                var_names=all_var_names,
                configured=configured_vars,
                ctx=ctx,
            )

            # Renderiza {{var}} no body usando os valores resolvidos. Caracteres
            # `{{` e `}}` que não bater com nenhum binding ficam como estão.
            rendered_body: str | None = None
            if body_text:
                rendered_body = _re.sub(
                    r"\{\{(\w+)\}\}",
                    lambda m: resolved_vars.get(m.group(1), m.group(0)),
                    body_text,
                )

            try:
                await self._chatnexo.send_template(
                    account_id=str(chatnexo_account_id),
                    conversation_id=str(conversation_id),
                    template_name=step.meta_template_name,
                    language=language,
                    variables=resolved_vars,
                    header_link=header_link,
                    header_kind=header_kind,
                    rendered_body=rendered_body,
                )
            except Exception as exc:
                reason = str(exc)[:500]
                await self._enrollment_repo.mark_failed(step.id, reason)
                log.warning(
                    "followup_step_send_failed",
                    step_id=str(step.id),
                    kind="template",
                    template=step.meta_template_name,
                    reason=reason,
                    exc_info=True,
                )
                return DispatchResult(
                    status=EnrollmentStepStatus.FAILED,
                    label="FAILED",
                    failure_reason=reason,
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
        return DispatchResult(status=EnrollmentStepStatus.SENT, label=dispatch_label)
