from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import structlog

from shared.config.settings import get_settings
from shared.domain.entities.access_case import AccessCase, AccessCaseStatus
from shared.domain.entities.scheduled_job import JobType
from shared.domain.events.purchase_received import PurchaseReceived
from shared.domain.ports.chatnexo import ChatNexoPort

log = structlog.get_logger(__name__)


class PurchaseHandler:
    def __init__(
        self,
        contact_repo: Any,
        chatnexo: ChatNexoPort,
        access_case_repo: Any,
        scheduler: Any,
        loja_express_case_repo: Any = None,
        loja_express_port: Any = None,
        criar_uc: Any = None,
        enroll_contact_uc: Any = None,
    ) -> None:
        self._contact_repo = contact_repo
        self._chatnexo = chatnexo
        self._access_case_repo = access_case_repo
        self._scheduler = scheduler
        self._loja_express_case_repo = loja_express_case_repo
        self._loja_express_port = loja_express_port
        self._criar_uc = criar_uc
        self._enroll_contact_uc = enroll_contact_uc

    async def execute(self, event: PurchaseReceived) -> None:
        settings = get_settings()
        account_id = str(event.account_id)

        contact = await self._contact_repo.find_or_create(
            account_id=account_id,
            phone=event.contact_phone,
            name=event.contact_name,
            email=event.contact_email,
        )

        conversation_id = await self._chatnexo.get_open_conversation(
            account_id=account_id, contact_phone=contact.phone
        )
        if conversation_id is None:
            conversation_id = await self._chatnexo.create_conversation(
                account_id=account_id, contact_phone=contact.phone
            )

        is_loja_express = any(
            tag in event.product.lower() for tag in settings.loja_express_product_tags
        )

        if is_loja_express and self._criar_uc is not None:
            await self._criar_uc.execute(
                account_id=int(event.account_id),
                contact_id=contact.id,
                conversation_id=conversation_id,
                purchase_id=event.purchase_id,
                product_name=event.product,
                student_email=event.contact_email,
                contact_name=event.contact_name,
            )
            log.info(
                "loja_express_purchase_routed",
                account_id=account_id,
                purchase_id=event.purchase_id,
            )
            return

        # Follow-up dinâmico (coexiste com Loja Express, exceto para produtos Loja Express)
        if not is_loja_express and self._enroll_contact_uc is not None:
            import uuid as _uuid
            contact_uuid = _uuid.UUID(str(contact.id))
            conv_uuid = _uuid.UUID(str(conversation_id))
            enrolled = await self._enroll_contact_uc.execute(
                account_id=event.account_id,
                contact_id=contact_uuid,
                conversation_id=conv_uuid,
                contact_phone=event.contact_phone,
                purchase_id=event.purchase_id,
                product=event.product,
                purchase_time=event.occurred_at,
            )
            if enrolled is not None:
                log.info(
                    "followup_enrolled_from_purchase",
                    enrollment_id=str(enrolled.id),
                    purchase_id=event.purchase_id,
                )

        # Normal welcome flow (Access capability)
        case = AccessCase(
            id=str(uuid4()),
            account_id=account_id,
            contact_id=contact.id,
            conversation_id=conversation_id,
            purchase_id=event.purchase_id,
            product_name=event.product,
            status=AccessCaseStatus.LINK_SENT,
        )
        await self._access_case_repo.save(case)

        await self._chatnexo.send_template(
            account_id=account_id,
            conversation_id=conversation_id,
            template_name="welcome_purchase",
            variables={"nome": event.contact_name, "produto": event.product},
        )

        # Legacy D+1 follow-up (mantido para compatibilidade — create_job não existe no scheduler)
        # await self._scheduler.schedule(
        #     account_id=event.account_id,
        #     conversation_id=UUID(str(conversation_id)),
        #     job_type=JobType.FOLLOWUP_D1,
        #     payload={},
        #     run_at=datetime.now(UTC) + timedelta(hours=24),
        # )

        log.info(
            "purchase_handled",
            account_id=account_id,
            purchase_id=event.purchase_id,
            conversation_id=conversation_id,
        )
