from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import structlog

from shared.config.single_tenant import DEFAULT_ACCOUNT_UUID
from shared.domain.value_objects.phone import Phone

log = structlog.get_logger(__name__)

_PURCHASE_EVENT_TYPES = frozenset({"subscription.activated"})


class HublaEventHandler:
    """Unified handler for any Hubla webhook event.

    Pipeline:
      1. Extract payer/product fields from the (variable-shape) payload.
      2. Resolve the Product by hubla_product_id.
      3. Look up FollowupFlows matching (product_id, trigger_event_type=event.type).
      4. For each matching flow: ensure ChatNexo conversation exists, then enroll contact.
      5. If event_type == subscription.activated: ALSO invoke PurchaseHandler.handle_one
         (preserves the existing welcome + access case behaviour).
    """

    def __init__(
        self,
        *,
        product_repo: Any,
        flow_repo: Any,
        contact_repo: Any,
        chatnexo: Any,
        enroll_contact_uc: Any,
        purchase_handler: Any,
        lead_repo: Any | None = None,
        hubla_event_repo: Any | None = None,
        account_id: UUID | None = None,
    ) -> None:
        self._product_repo = product_repo
        self._flow_repo = flow_repo
        self._contact_repo = contact_repo
        self._chatnexo = chatnexo
        self._enroll_contact_uc = enroll_contact_uc
        self._purchase_handler = purchase_handler
        self._lead_repo = lead_repo
        self._hubla_event_repo = hubla_event_repo
        self._account_id = account_id or DEFAULT_ACCOUNT_UUID

    async def handle(self, payload: dict[str, Any]) -> None:
        event_type: str = payload.get("type", "")
        event = payload.get("event", {})
        subscription = event.get("subscription", {})
        payer = subscription.get("payer", {})
        products_list = event.get("products") or []
        product_data = products_list[0] if products_list else event.get("product", {})

        hubla_product_id: str = product_data.get("id", "")
        product_name: str = product_data.get("name", "")
        purchase_id: str = subscription.get("id", "")
        payer_phone: str = payer.get("phone", "")
        payer_email: str = payer.get("email", "")
        payer_full_name: str = (
            payer.get("firstName", "") + " " + payer.get("lastName", "")
        ).strip()
        payer_document: str = payer.get("document", "")
        activated_at_raw: str = subscription.get("activatedAt", "")
        try:
            activated_at = datetime.fromisoformat(activated_at_raw.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            activated_at = datetime.now(UTC)

        account_uuid = self._account_id
        account_id_str = str(account_uuid)

        # === PR 4: persist event/lead FIRST — captura tudo, mesmo sem phone ===

        # Extra fields from variable-shape payloads
        first_session = subscription.get("firstPaymentSession") or {}
        utm = first_session.get("utm") or {}
        last_invoice = subscription.get("lastInvoice") or {}
        amount = last_invoice.get("amount") or {}
        offers = product_data.get("offers") or []
        first_offer = offers[0] if offers else {}
        cookies = first_session.get("cookies") or {}
        sub_status = subscription.get("status", "unknown")

        # Persist HublaEvent (log imutável). Best-effort: if repo not injected, skip.
        if self._hubla_event_repo is not None:
            await self._hubla_event_repo.insert(
                account_id=account_uuid,
                event_type=event_type,
                hubla_subscription_id=purchase_id,
                hubla_product_id=hubla_product_id,
                product_name=product_name,
                payer_phone=payer_phone,
                payer_email=payer_email,
                payer_name=payer_full_name,
                payload=payload,
            )

        # Upsert Lead (visão materializada com UTMs, valor, sessão).
        # Chave natural é (account_id, hubla_subscription_id) — não depende de phone.
        if self._lead_repo is not None and purchase_id:
            await self._lead_repo.upsert(
                account_id=account_uuid,
                hubla_subscription_id=purchase_id,
                event_type=event_type,
                payer_phone=payer_phone,
                payer_name=payer_full_name,
                payer_email=payer_email,
                payer_document=payer.get("document") or None,
                hubla_product_id=hubla_product_id,
                product_name=product_name,
                offer_id=first_offer.get("id") or None,
                offer_name=first_offer.get("name") or None,
                amount_total_cents=amount.get("totalCents"),
                amount_subtotal_cents=amount.get("subtotalCents"),
                payment_method=subscription.get("paymentMethod"),
                subscription_status=sub_status,
                utm_source=utm.get("source") or None,
                utm_medium=utm.get("medium") or None,
                utm_campaign=utm.get("campaign") or None,
                utm_content=utm.get("content") or None,
                utm_term=utm.get("term") or None,
                session_ip=first_session.get("ip") or None,
                session_url=first_session.get("url") or None,
                fbp=cookies.get("fbp") or None,
                event_at=activated_at,
            )

        # === End PR 4 early persistence ===

        if not payer_phone:
            log.warning("hubla_event_no_phone", event_type=event_type, purchase_id=purchase_id)
            return

        product = await self._product_repo.find_active_by_hubla_id(account_uuid, hubla_product_id)

        if product is None:
            log.warning(
                "hubla_event_product_not_found",
                event_type=event_type,
                hubla_product_id=hubla_product_id,
            )
            # Para subscription.activated, mantém comportamento legado (welcome + access case)
            # mesmo sem curso cadastrado no catálogo — garante que nenhuma compra seja ignorada.
            if event_type in _PURCHASE_EVENT_TYPES:
                await self._purchase_handler.handle_one(
                    hubla_product_id=hubla_product_id,
                    product_name=product_name,
                    purchase_id=purchase_id,
                    activated_at=activated_at,
                    payer_phone=payer_phone,
                    payer_email=payer_email,
                    payer_full_name=payer_full_name,
                    payer_document=payer_document,
                    account_id=account_uuid,
                )
            # TODO(PR4): para outros event types com produto desconhecido (lead.abandoned, etc),
            # ainda salvamos em hubla_events + leads para análise posterior.
            # Por enquanto: drop silencioso (apenas o log.warning acima).
            return

        contact = await self._contact_repo.upsert(
            account_id=account_uuid,
            phone=Phone.parse(payer_phone),
            name=payer_full_name,
            email=payer_email,
        )

        flows = await self._flow_repo.list_active_by_product_and_event(
            product_id=product.id, event_type=event_type
        )

        for flow in flows:
            conversation_id = await self._chatnexo.get_open_conversation(
                account_id=account_id_str, contact_phone=contact.phone
            )
            if conversation_id is None:
                conversation_id = await self._chatnexo.create_conversation(
                    account_id=account_id_str, contact_phone=contact.phone
                )
            await self._enroll_contact_uc.execute(
                account_id=account_uuid,
                contact_id=UUID(str(contact.id)),
                conversation_id=str(conversation_id),
                contact_phone=payer_phone,
                purchase_id=purchase_id,
                flow_id=flow.id,
                customer_name=payer_full_name,
                product_name=product_name,
                purchase_time=activated_at,
            )

        log.info(
            "hubla_event_flows_enrolled",
            event_type=event_type,
            product_id=str(product.id),
            flows=len(flows),
            purchase_id=purchase_id,
        )

        # For subscription.activated, also run the legacy PurchaseHandler (welcome + access case).
        if event_type in _PURCHASE_EVENT_TYPES:
            await self._purchase_handler.handle_one(
                hubla_product_id=hubla_product_id,
                product_name=product_name,
                purchase_id=purchase_id,
                activated_at=activated_at,
                payer_phone=payer_phone,
                payer_email=payer_email,
                payer_full_name=payer_full_name,
                payer_document=payer_document,
                account_id=account_uuid,
            )
