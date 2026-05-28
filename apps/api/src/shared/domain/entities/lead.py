from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(slots=True)
class Lead:
    """Visão materializada de um lead — atualizada via upsert a cada evento Hubla relevante.

    Chave natural: (account_id, hubla_subscription_id). UTMs e dados de sessão
    são preservados na primeira inserção; eventos subsequentes só atualizam
    status, last_event_*, contact_id e activated_at (quando aplicável).
    """

    id: UUID
    account_id: UUID
    hubla_subscription_id: str
    payer_phone: str
    payer_name: str
    payer_email: str
    hubla_product_id: str
    product_name: str
    subscription_status: str
    first_seen_at: datetime
    last_event_at: datetime
    last_event_type: str
    created_at: datetime
    updated_at: datetime
    contact_id: UUID | None = None
    payer_document: str | None = None
    offer_id: str | None = None
    offer_name: str | None = None
    amount_total_cents: int | None = None
    amount_subtotal_cents: int | None = None
    payment_method: str | None = None
    utm_source: str | None = None
    utm_medium: str | None = None
    utm_campaign: str | None = None
    utm_content: str | None = None
    utm_term: str | None = None
    session_ip: str | None = None
    session_url: str | None = None
    fbp: str | None = None
    activated_at: datetime | None = None
    chatnexo_conversation_url: str | None = None
