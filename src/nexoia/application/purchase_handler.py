from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import structlog

from nexoia.domain.entities.access_case import AccessCase, AccessCaseStatus
from nexoia.domain.entities.scheduled_job import JobType
from nexoia.domain.events.purchase_received import PurchaseReceived
from nexoia.domain.ports.chatnexo import ChatNexoPort

log = structlog.get_logger(__name__)


class PurchaseHandler:
    def __init__(
        self,
        contact_repo: Any,
        chatnexo: ChatNexoPort,
        access_case_repo: Any,
        scheduler: Any,
    ) -> None:
        self._contact_repo = contact_repo
        self._chatnexo = chatnexo
        self._access_case_repo = access_case_repo
        self._scheduler = scheduler

    async def execute(self, event: PurchaseReceived) -> None:
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

        await self._scheduler.create_job(
            job_type=JobType.FOLLOWUP_D1,
            account_id=account_id,
            conversation_id=conversation_id,
            run_at=datetime.now(UTC) + timedelta(hours=24),
        )

        log.info(
            "purchase_handled",
            account_id=account_id,
            purchase_id=event.purchase_id,
            conversation_id=conversation_id,
        )
