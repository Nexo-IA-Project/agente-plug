from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import structlog

from shared.domain.entities.access_case import AccessCase, AccessCaseStatus
from shared.domain.events.purchase_received import PurchaseReceived
from shared.domain.ports.chatnexo import ChatNexoPort
from shared.domain.value_objects.phone import Phone

log = structlog.get_logger(__name__)

# Sistema single-tenant: account_id fixo.
_DEFAULT_ACCOUNT_UUID = UUID("00000000-0000-0000-0000-000000000001")


class PurchaseHandler:
    """Processa a parte de Access (welcome message + access case) de uma compra Hubla.

    Enrollment em flows é responsabilidade do HublaEventHandler — este handler
    NÃO toca em FollowupFlow nem FollowupEnrollment.
    """

    def __init__(
        self,
        contact_repo: Any,
        chatnexo: ChatNexoPort,
        access_case_repo: Any,
        scheduler: Any,
        product_repo: Any,
    ) -> None:
        self._contact_repo = contact_repo
        self._chatnexo = chatnexo
        self._access_case_repo = access_case_repo
        self._scheduler = scheduler
        self._product_repo = product_repo

    async def handle_one(
        self,
        *,
        hubla_product_id: str,
        product_name: str,
        purchase_id: str,
        activated_at: datetime,
        payer_phone: str,
        payer_email: str,
        payer_full_name: str,
        payer_document: str,
        account_id: UUID | None = None,
    ) -> None:
        """Processa a parte de Access (welcome + access case) de um produto de compra Hubla.

        Enrollment em flows é responsabilidade do HublaEventHandler — este handler
        NÃO toca em FollowupFlow nem FollowupEnrollment.
        """
        account_uuid = account_id or _DEFAULT_ACCOUNT_UUID
        account_id_str = str(account_uuid)

        contact = await self._contact_repo.upsert(
            account_id=account_uuid,
            phone=Phone.parse(payer_phone),
            name=payer_full_name,
            email=payer_email,
        )

        conversation_id = await self._chatnexo.get_open_conversation(
            account_id=account_id_str, contact_phone=contact.phone
        )
        if conversation_id is None:
            conversation_id = await self._chatnexo.create_conversation(
                account_id=account_id_str, contact_phone=contact.phone
            )

        # Access capability — sempre executa.
        case = AccessCase(
            id=str(uuid4()),
            account_id=account_id_str,
            contact_id=contact.id,
            conversation_id=conversation_id,
            purchase_id=purchase_id,
            product_name=product_name,
            status=AccessCaseStatus.LINK_SENT,
        )
        await self._access_case_repo.save(case)

        await self._chatnexo.send_template(
            account_id=account_id_str,
            conversation_id=conversation_id,
            template_name="welcome_purchase",
            variables={"nome": payer_full_name, "produto": product_name},
        )

        log.info(
            "purchase_handled",
            account_id=account_id_str,
            purchase_id=purchase_id,
            conversation_id=conversation_id,
            product_id=hubla_product_id,
        )

    async def execute(self, event: PurchaseReceived) -> None:
        """Alias legado para `handle_one` — recebe um PurchaseReceived event."""
        await self.handle_one(
            hubla_product_id=event.product_id,
            product_name=event.product_name,
            purchase_id=event.purchase_id,
            activated_at=event.occurred_at,
            payer_phone=event.contact_phone,
            payer_email=event.contact_email,
            payer_full_name=event.customer_name,
            payer_document="",
            account_id=event.account_id,
        )
