from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog

from shared.config.settings import get_settings
from shared.domain.entities.refund_case import RefundCase, RefundCaseStatus
from shared.domain.ports.hubla_port import HublaPort

log = structlog.get_logger(__name__)


class VerificarElegibilidadeReembolso:
    def __init__(
        self,
        refund_repo: Any,
        hubla: HublaPort,
        legal_history: Any,
    ) -> None:
        self._repo = refund_repo
        self._hubla = hubla
        self._legal_history = legal_history

    async def execute(
        self,
        account_id: int,
        phone: str,
        conversation_id: str,
        motivo: str,
        email: str,
        cpf: str,
    ) -> str:
        case = RefundCase(
            account_id=account_id,
            contact_id=phone,
            conversation_id=conversation_id,
            student_email=email,
            student_cpf=cpf,
            refund_reason=motivo,
            status=RefundCaseStatus.CHECKING_DEADLINE,
        )
        await self._repo.save(case)

        # RF-R19: fetch purchase BEFORE any mention of deadline
        purchase = await self._hubla.get_purchase_by_email(email, account_id)
        if purchase is None:
            log.warning("purchase_not_found", email=email, account_id=account_id)
            case.status = RefundCaseStatus.ESCALATED
            await self._repo.update(case)
            return "COMPRA_NAO_ENCONTRADA: Não foi possível localizar compra para este email."

        deadline_days = get_settings().refund_deadline_days
        today = datetime.now(UTC).date()

        # RF-R13: recurring → use first_charge_at
        if purchase.is_recurring and purchase.first_charge_at is not None:
            base_date = purchase.first_charge_at.date()
        else:
            base_date = purchase.created_at.date()

        days = (today - base_date).days

        case.purchase_id = purchase.id
        case.product_name = purchase.product_name
        case.days_since_purchase = days

        # RF-R03: Art. 49 — prior mention on any channel within deadline
        has_prior = await self._legal_history.has_prior_refund_mention(
            account_id=account_id,
            contact_id=phone,
            purchase_date=(
                purchase.first_charge_at
                if (purchase.is_recurring and purchase.first_charge_at)
                else purchase.created_at
            ),
        )

        within = days <= deadline_days or has_prior
        case.within_deadline = within

        # RF-R04: duplicate purchase → skip retention
        if purchase.is_duplicate:
            case.is_duplicate_purchase = True
            await self._repo.update(case)
            log.info("duplicate_purchase", case_id=case.id)
            return f"COMPRA_DUPLICADA: case_id={case.id}, product={purchase.product_name}"

        if within:
            await self._repo.update(case)
            log.info("eligible_for_refund", case_id=case.id, days=days)
            return f"ELEGIVEL: case_id={case.id}, dias={days}, produto={purchase.product_name}"

        case.status = RefundCaseStatus.DENIED
        await self._repo.update(case)
        purchase_date_str = base_date.strftime("%d/%m/%Y")
        log.info("refund_denied_deadline", case_id=case.id, days=days)
        return f"INELEGIVEL: case_id={case.id}, data_compra={purchase_date_str}, dias={days}"
