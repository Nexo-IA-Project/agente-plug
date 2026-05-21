from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import structlog

from shared.domain.entities.access_case import AccessCase, AccessCaseStatus
from shared.domain.events.purchase_received import PurchaseReceived
from shared.domain.ports.chatnexo import ChatNexoPort

log = structlog.get_logger(__name__)


class PurchaseHandler:
    """
    Processa eventos de compra:
      1. Cria/encontra contato e abre conversa.
      2. Tenta resolver o produto via course_repo.find_active_by_hubla_id (event.product_id).
         - Curso encontrado: enrolla contato em todos os flows ativos do curso.
         - Curso não encontrado: loga warning e segue sem enrollment.
      3. Sempre cria AccessCase e dispara welcome_purchase template (Access capability).
    """

    def __init__(
        self,
        contact_repo: Any,
        chatnexo: ChatNexoPort,
        access_case_repo: Any,
        scheduler: Any,
        course_repo: Any,
        flow_repo: Any,
        enroll_contact_uc: Any,
    ) -> None:
        self._contact_repo = contact_repo
        self._chatnexo = chatnexo
        self._access_case_repo = access_case_repo
        self._scheduler = scheduler
        self._course_repo = course_repo
        self._flow_repo = flow_repo
        self._enroll_contact_uc = enroll_contact_uc

    async def execute(self, event: PurchaseReceived) -> None:
        account_id = str(event.account_id)

        contact = await self._contact_repo.find_or_create(
            account_id=account_id,
            phone=event.contact_phone,
            name=event.customer_name,
            email=event.contact_email,
        )

        conversation_id = await self._chatnexo.get_open_conversation(
            account_id=account_id, contact_phone=contact.phone
        )
        if conversation_id is None:
            conversation_id = await self._chatnexo.create_conversation(
                account_id=account_id, contact_phone=contact.phone
            )

        # Resolve curso via hubla_id (matching usa product_id).
        course = await self._course_repo.find_active_by_hubla_id(event.account_id, event.product_id)
        if course is None:
            log.warning(
                "course_not_found",
                product_id=event.product_id,
                account_id=account_id,
            )
        else:
            flows = await self._flow_repo.list_active_by_course(course.id)
            for flow in flows:
                await self._enroll_contact_uc.execute(
                    account_id=event.account_id,
                    contact_id=UUID(str(contact.id)),
                    conversation_id=str(conversation_id),
                    contact_phone=event.contact_phone,
                    purchase_id=event.purchase_id,
                    flow_id=flow.id,
                    customer_name=event.customer_name,
                    product_name=event.product_name,
                    purchase_time=event.occurred_at,
                )
            log.info(
                "followup_enrollments_dispatched",
                course_id=str(course.id),
                flows=len(flows),
                purchase_id=event.purchase_id,
            )

        # Access capability — sempre executa.
        case = AccessCase(
            id=str(uuid4()),
            account_id=account_id,
            contact_id=contact.id,
            conversation_id=conversation_id,
            purchase_id=event.purchase_id,
            product_name=event.product_name,
            status=AccessCaseStatus.LINK_SENT,
        )
        await self._access_case_repo.save(case)

        await self._chatnexo.send_template(
            account_id=account_id,
            conversation_id=conversation_id,
            template_name="welcome_purchase",
            variables={"nome": event.customer_name, "produto": event.product_name},
        )

        log.info(
            "purchase_handled",
            account_id=account_id,
            purchase_id=event.purchase_id,
            conversation_id=conversation_id,
        )
