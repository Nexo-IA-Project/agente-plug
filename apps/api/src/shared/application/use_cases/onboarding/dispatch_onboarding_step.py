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
        flow_repo: Any | None = None,
        leads_pubsub: Any | None = None,
        session: Any | None = None,
    ) -> None:
        self._enrollment_repo = enrollment_repo
        self._contact_repo = contact_repo
        self._chatnexo = chatnexo
        self._history = conversation_history
        self._template_repo = meta_template_repo
        # flow_repo é opcional pra retro-compat com chamadas antigas; quando
        # presente, o use case checa flow.is_active antes de disparar e cancela
        # steps de flows pausados.
        self._flow_repo = flow_repo
        # leads_pubsub + session são opcionais; quando presentes, o use case
        # publica `lead.enrollment.updated` no Redis após cada mudança de status
        # de step (sucesso, falha, cancelamento) — alimenta o SSE de leads.
        self._leads_pubsub = leads_pubsub
        self._session = session

    async def _publish_enrollment_updated(
        self,
        *,
        enrollment: Any,
        step: Any,
        step_status: EnrollmentStepStatus,
        step_label: str,
    ) -> None:
        """Publica `lead.enrollment.updated` no Redis após mudança de status.

        No-op quando `leads_pubsub` não foi injetado. Falhas no publish são
        logadas mas nunca propagadas — pub/sub não pode quebrar o pipeline.
        """
        if self._leads_pubsub is None:
            return
        if enrollment is None:
            return

        lead_id: str | None = None
        if self._session is not None and getattr(enrollment, "contact_id", None) is not None:
            try:
                from sqlalchemy import select

                from shared.adapters.db.models import LeadModel

                result = await self._session.execute(
                    select(LeadModel.id)
                    .where(
                        LeadModel.account_id == enrollment.account_id,
                        LeadModel.contact_id == enrollment.contact_id,
                    )
                    .order_by(LeadModel.last_event_at.desc())
                    .limit(1)
                )
                row = result.scalar_one_or_none()
                if row is not None:
                    lead_id = str(row)
            except Exception as exc:
                log.warning("dispatch_lead_lookup_failed", error=str(exc))

        enrollment_status = getattr(enrollment, "status", None)
        envelope = {
            "type": "lead.enrollment.updated",
            "lead_id": lead_id,
            "enrollment": {
                "id": str(enrollment.id),
                "status": enrollment_status.value
                if hasattr(enrollment_status, "value")
                else str(enrollment_status)
                if enrollment_status is not None
                else None,
                "step_id": str(step.id),
                "step_status": step_status.value
                if hasattr(step_status, "value")
                else str(step_status),
                "step_label": step_label,
            },
        }
        try:
            await self._leads_pubsub.publish(enrollment.account_id, envelope)
        except Exception as exc:
            log.warning("dispatch_publish_failed", error=str(exc))

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

        # Cache do enrollment carregado durante a execute(); reaproveitado para
        # publicar `lead.enrollment.updated` em cada caminho de saída sem
        # bater no DB de novo.
        cached_enrollment: Any = None

        # Bloqueia disparo se o flow do enrollment estiver desativado.
        # Sem essa check, scheduled_jobs criados antes da desativação continuam
        # enviando mesmo com flow.is_active=False.
        if self._flow_repo is not None:
            enrollment = await self._enrollment_repo.find_enrollment_by_id(step.enrollment_id)
            cached_enrollment = enrollment
            if enrollment is not None and enrollment.flow_id is not None:
                flow = await self._flow_repo.find_by_id(enrollment.flow_id)
                if flow is None or not flow.is_active:
                    reason = "flow_inactive"
                    log.info(
                        "followup_step_cancelled_flow_inactive",
                        step_id=str(step.id),
                        flow_id=str(enrollment.flow_id),
                    )
                    await self._enrollment_repo.mark_cancelled(step.id, reason)
                    step.status = EnrollmentStepStatus.CANCELLED
                    await self._publish_enrollment_updated(
                        enrollment=enrollment,
                        step=step,
                        step_status=EnrollmentStepStatus.CANCELLED,
                        step_label="CANCELADO: flow desativado",
                    )
                    return DispatchResult(
                        status=EnrollmentStepStatus.CANCELLED,
                        label="CANCELADO: flow desativado",
                        failure_reason=reason,
                    )

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
                if cached_enrollment is None:
                    cached_enrollment = await self._enrollment_repo.find_enrollment_by_id(
                        step.enrollment_id
                    )
                step.status = EnrollmentStepStatus.FAILED
                await self._publish_enrollment_updated(
                    enrollment=cached_enrollment,
                    step=step,
                    step_status=EnrollmentStepStatus.FAILED,
                    step_label="FAILED",
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
            parameter_format: str = "NAMED"

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
                    body_node = next(
                        (c for c in components if c.get("type") == "BODY"),
                        None,
                    )
                    body_text = body_node.get("text") if body_node else None
                    # Detecta parameter_format em duas etapas:
                    #   1) `example` do componente (sinal primário, populado quando o
                    #      template é syncado com a Meta);
                    #   2) Fallback: inspecionar o próprio texto — `{{1}}`, `{{2}}` →
                    #      POSITIONAL; `{{customer_name}}` → NAMED. Necessário pra
                    #      templates importados via dump sem `example`.
                    detected: str | None = None
                    if body_node and isinstance(body_node.get("example"), dict):
                        if "body_text_named_params" in body_node["example"]:
                            detected = "NAMED"
                        elif "body_text" in body_node["example"]:
                            detected = "POSITIONAL"
                    if detected is None and body_text:
                        placeholders = _re.findall(r"\{\{(\w+)\}\}", body_text)
                        if placeholders:
                            detected = (
                                "POSITIONAL" if all(p.isdigit() for p in placeholders) else "NAMED"
                            )
                    if detected is not None:
                        parameter_format = detected
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
            cached_enrollment = enrollment
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
                    parameter_format=parameter_format,  # type: ignore[arg-type]
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
                step.status = EnrollmentStepStatus.FAILED
                await self._publish_enrollment_updated(
                    enrollment=cached_enrollment,
                    step=step,
                    step_status=EnrollmentStepStatus.FAILED,
                    step_label="FAILED",
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
            # Atualiza o status do enrollment cached para que o envelope publicado
            # reflita o estado pós-update (COMPLETED) ao invés do estado anterior.
            if cached_enrollment is not None:
                import contextlib

                with contextlib.suppress(Exception):
                    cached_enrollment.status = EnrollmentStatus.COMPLETED

        if cached_enrollment is None:
            cached_enrollment = await self._enrollment_repo.find_enrollment_by_id(
                step.enrollment_id
            )
        await self._publish_enrollment_updated(
            enrollment=cached_enrollment,
            step=step,
            step_status=EnrollmentStepStatus.SENT,
            step_label=dispatch_label,
        )

        log.info(
            "followup_step_dispatched",
            step_id=str(step.id),
            template=step.meta_template_name,
            has_text=bool(step.message_text),
        )
        return DispatchResult(status=EnrollmentStepStatus.SENT, label=dispatch_label)
