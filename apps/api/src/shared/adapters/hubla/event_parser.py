from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class ParsedProduct:
    hubla_id: str
    name: str


@dataclass(frozen=True)
class ParsedPurchaseEvent:
    purchase_id: str
    activated_at: datetime
    payer_phone: str
    payer_email: str
    payer_full_name: str
    payer_document: str
    products: list[ParsedProduct]


class HublaEventParser:
    """Parse de webhooks Hubla v2.0.0 (subscription.activated)."""

    def parse(self, payload: dict[str, Any]) -> ParsedPurchaseEvent:
        event_type = payload.get("type")
        if event_type != "subscription.activated":
            raise ValueError(f"unsupported event type: {event_type}")

        event = payload["event"]
        subscription = event["subscription"]
        payer = subscription["payer"]

        raw_products = event.get("products")
        if not raw_products:
            single = event.get("product")
            raw_products = [single] if single else []
        products = [ParsedProduct(hubla_id=p["id"], name=p.get("name", "")) for p in raw_products]

        full_name = " ".join(
            x for x in (payer.get("firstName"), payer.get("lastName")) if x
        ).strip()

        return ParsedPurchaseEvent(
            purchase_id=str(subscription["id"]),
            activated_at=datetime.fromisoformat(subscription["activatedAt"].replace("Z", "+00:00")),
            payer_phone=payer["phone"],
            payer_email=payer.get("email", ""),
            payer_full_name=full_name,
            payer_document=payer.get("document", ""),
            products=products,
        )
