from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import structlog

from shared.adapters.hubla.v1_normalizer import is_v1_payload, normalize_v1_payload
from shared.config.single_tenant import DEFAULT_ACCOUNT_UUID
from shared.domain.entities.hubla_event import HublaEvent
from shared.domain.entities.lead import Lead
from shared.domain.value_objects.hubla_event_type import (
    PURCHASE_EVENT_TYPES,
    is_valid_hubla_event_type,
    normalize_event_type,
)
from shared.domain.value_objects.phone import Phone

log = structlog.get_logger(__name__)


def _lead_to_dict(lead: Lead) -> dict[str, Any]:
    """Serializa Lead pro envelope SSE — mesmo shape do LeadResponse no router."""
    return {
        "id": str(lead.id),
        "hubla_subscription_id": lead.hubla_subscription_id,
        "payer_phone": lead.payer_phone,
        "payer_name": lead.payer_name,
        "payer_email": lead.payer_email,
        "payer_document": lead.payer_document,
        "hubla_product_id": lead.hubla_product_id,
        "product_name": lead.product_name,
        "offer_name": lead.offer_name,
        "amount_total_cents": lead.amount_total_cents,
        "payment_method": lead.payment_method,
        "subscription_status": lead.subscription_status,
        "utm_source": lead.utm_source,
        "utm_campaign": lead.utm_campaign,
        "first_seen_at": lead.first_seen_at.isoformat() if lead.first_seen_at else None,
        "activated_at": lead.activated_at.isoformat() if lead.activated_at else None,
        "last_event_at": lead.last_event_at.isoformat() if lead.last_event_at else None,
        "last_event_type": lead.last_event_type,
        "chatnexo_conversation_url": lead.chatnexo_conversation_url,
    }


def _hubla_event_to_dict(event: HublaEvent) -> dict[str, Any]:
    return {
        "id": str(event.id),
        "event_type": event.event_type,
        "received_at": event.received_at.isoformat() if event.received_at else None,
        "payer_phone": event.payer_phone,
        "product_name": event.product_name,
    }


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
        leads_pubsub: Any | None = None,
        account_id: UUID | None = None,
        chatnexo_account_id: int = 1,
        chatnexo_inbox_id: int = 1,
    ) -> None:
        self._product_repo = product_repo
        self._flow_repo = flow_repo
        self._contact_repo = contact_repo
        self._chatnexo = chatnexo
        self._enroll_contact_uc = enroll_contact_uc
        self._purchase_handler = purchase_handler
        self._lead_repo = lead_repo
        self._hubla_event_repo = hubla_event_repo
        self._leads_pubsub = leads_pubsub
        self._account_id = account_id or DEFAULT_ACCOUNT_UUID
        self._chatnexo_account_id = chatnexo_account_id
        self._chatnexo_inbox_id = chatnexo_inbox_id

    async def handle(self, payload: dict[str, Any]) -> None:
        # Hubla mantém 2 versões de webhook coexistindo (v1.0.0 legacy + v2.0.0 atual).
        # Se vier v1 (ex: type=NewSale), converte pro formato v2 antes do pipeline ler
        # os campos. Caso contrário avisa o cliente pra atualizar a regra no painel
        # pra (v2) — mas processamos mesmo assim.
        if is_v1_payload(payload):
            log.warning(
                "hubla_v1_payload_normalized",
                original_type=payload.get("type"),
                hint="atualize a regra no painel Hubla para eventos (v2)",
            )
            payload = normalize_v1_payload(payload)

        # Normaliza nomes de eventos legados (ex: member.access_granted → customer.member_added).
        # Defesa em profundidade: caso algum payload chegue com o nome velho do enum
        # antigo, mapeia pro nome correto da Hubla v2 antes de prosseguir.
        event_type: str = normalize_event_type(payload.get("type", ""))
        if event_type and not is_valid_hubla_event_type(event_type):
            log.warning(
                "hubla_unknown_event",
                event_type=event_type,
                payload_id=payload.get("id"),
            )
        # Continuar pipeline mesmo em evento desconhecido — persistir em hubla_events para análise.
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

        # === PR 4 review fix #6: resolve Contact FIRST so contact_id is available
        # when persisting hubla_events and leads (FK must be populated for known contacts).
        # Normaliza telefone uma vez — usado em TODOS os calls downstream pra evitar
        # divergência entre o que está no DB e o que é passado ao ChatNexo/PurchaseHandler.
        contact: Any | None = None
        payer_phone_e164: str = ""
        if payer_phone:
            try:
                parsed_phone = Phone.parse(payer_phone)
                payer_phone_e164 = str(parsed_phone)
                contact = await self._contact_repo.upsert(
                    account_id=account_uuid,
                    phone=parsed_phone,
                    name=payer_full_name,
                    email=payer_email,
                )
            except Exception as exc:
                # Phone inválido: log e segue sem contact — event/lead ainda são persistidos
                # com o phone raw pra análise posterior.
                log.warning(
                    "hubla_event_invalid_phone",
                    event_type=event_type,
                    purchase_id=purchase_id,
                    raw_phone=payer_phone,
                    error=str(exc),
                )

        contact_id_uuid: UUID | None = None
        if contact is not None:
            cid = contact.id
            contact_id_uuid = cid if isinstance(cid, UUID) else UUID(str(cid))

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
        # PR 4 review fix #6: contact_id populated when contact was resolved above.
        # PR 4 review fix #12: processed_at will be set via mark_processed in try/finally below.
        event_model = None
        if self._hubla_event_repo is not None:
            event_model = await self._hubla_event_repo.insert(
                account_id=account_uuid,
                event_type=event_type,
                hubla_subscription_id=purchase_id,
                hubla_product_id=hubla_product_id,
                product_name=product_name,
                payer_phone=payer_phone,
                payer_email=payer_email,
                payer_name=payer_full_name,
                contact_id=contact_id_uuid,
                payload=payload,
            )

        # Upsert Lead (visão materializada com UTMs, valor, sessão).
        # Chave natural é (account_id, hubla_subscription_id) — não depende de phone.
        # PR 4 review fix #6: contact_id populated when contact was resolved above.
        lead_entity: Lead | None = None
        if self._lead_repo is not None and purchase_id:
            lead_entity = await self._lead_repo.upsert(
                account_id=account_uuid,
                hubla_subscription_id=purchase_id,
                event_type=event_type,
                contact_id=contact_id_uuid,
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

        # Real-time: publica lead.upserted no canal Redis pro stream SSE.
        # is_new é heurística: insert novo tem created_at == updated_at; updates
        # subsequentes só mexem em updated_at. Suficiente pro frontend decidir
        # "prepend nova linha" vs "atualizar linha existente".
        if self._leads_pubsub is not None and lead_entity is not None:
            is_new = lead_entity.created_at == lead_entity.updated_at
            envelope: dict[str, Any] = {
                "type": "lead.upserted",
                "is_new": is_new,
                "lead": _lead_to_dict(lead_entity),
            }
            if event_model is not None:
                envelope["event"] = _hubla_event_to_dict(event_model)
            await self._leads_pubsub.publish(account_uuid, envelope)

        # === End PR 4 early persistence ===

        # PR 4 review fix #12: mark processed_at at every exit point (try/finally).
        try:
            await self._route(
                event_type=event_type,
                account_uuid=account_uuid,
                account_id_str=account_id_str,
                contact=contact,
                payer_phone=payer_phone_e164,
                payer_email=payer_email,
                payer_full_name=payer_full_name,
                payer_document=payer_document,
                hubla_product_id=hubla_product_id,
                product_name=product_name,
                purchase_id=purchase_id,
                activated_at=activated_at,
            )
        finally:
            if event_model is not None and self._hubla_event_repo is not None:
                await self._hubla_event_repo.mark_processed(event_model.id)

    async def _route(
        self,
        *,
        event_type: str,
        account_uuid: UUID,
        account_id_str: str,
        contact: Any | None,
        payer_phone: str,
        payer_email: str,
        payer_full_name: str,
        payer_document: str,
        hubla_product_id: str,
        product_name: str,
        purchase_id: str,
        activated_at: datetime,
    ) -> None:
        """Roteamento interno: enrollment de flows + PurchaseHandler legado."""
        if not payer_phone or contact is None:
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
            if event_type in PURCHASE_EVENT_TYPES:
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

        # contact is guaranteed non-None here (checked at top of _route)
        flows = await self._flow_repo.list_active_by_product_and_event(
            product_id=product.id, event_type=event_type
        )

        # ChatNexo (Chatwoot fork) usa account_id como integer; o UUID local não bate.
        chatnexo_account_id = str(self._chatnexo_account_id)

        for flow in flows:
            conversation_id = await self._chatnexo.get_open_conversation(
                account_id=chatnexo_account_id, contact_phone=str(contact.phone)
            )
            if conversation_id is None:
                conversation_id = await self._chatnexo.create_conversation(
                    account_id=chatnexo_account_id,
                    contact_phone=str(contact.phone),
                    inbox_id=self._chatnexo_inbox_id,
                    contact_name=payer_full_name or None,
                    contact_email=payer_email or None,
                )
            await self._enroll_contact_uc.execute(
                account_id=account_uuid,
                contact_id=UUID(str(contact.id)),
                conversation_id=str(conversation_id),
                contact_phone=str(contact.phone),
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
        if event_type in PURCHASE_EVENT_TYPES:
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
