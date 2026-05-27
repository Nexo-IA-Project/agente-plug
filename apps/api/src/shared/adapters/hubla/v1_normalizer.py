"""Normaliza payloads Hubla v1.0.0 (legacy) para o formato v2.0.0.

A Hubla mantém 2 versões de webhook coexistindo:

- **v1.0.0** — formato legacy, ex: `{"type": "NewSale", "event": {...campos achatados...}}`
- **v2.0.0** — formato novo, ex: `{"type": "subscription.activated", "event": {"subscription": {...}}}`

O resto do pipeline (`HublaEventHandler`) só entende v2. Esse módulo é o ponto
único de tradução — chama uma vez no início do handler. Evita ramificar a
lógica downstream.

Eventos suportados (todos os types v1 conhecidos):

| v1 `type`             | v2 `type`                       |
|-----------------------|---------------------------------|
| `NewSale`             | `subscription.activated`        |
| `Renewal`             | `subscription.activated`        |
| `Canceled`            | `subscription.deactivated`      |
| `Expired`             | `subscription.expiring`         |
| `ChargedBack`         | `invoice.refunded`              |
| `Refund`              | `invoice.refunded`              |
| `AbandonedCart`       | `lead.abandoned_checkout`       |

Eventos v1 com `type` não mapeado passam adiante inalterados — o handler
loga como `hubla_unknown_event` e persiste em `hubla_events` para auditoria.
"""

from __future__ import annotations

from typing import Any

# Mapa v1 type → v2 type. Cobre os tipos mais comuns documentados da Hubla v1.
_V1_TO_V2_EVENT_MAP: dict[str, str] = {
    "NewSale": "subscription.activated",
    "Renewal": "subscription.activated",
    "Canceled": "subscription.deactivated",
    "Expired": "subscription.expiring",
    "ChargedBack": "invoice.refunded",
    "Refund": "invoice.refunded",
    "AbandonedCart": "lead.abandoned_checkout",
}


def is_v1_payload(payload: dict[str, Any]) -> bool:
    """Detecta se o payload é Hubla v1.0.0 (qualquer versão da família 1.x)."""
    return str(payload.get("version", "")).startswith("1.")


def normalize_v1_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Converte payload v1 → v2. Retorna inalterado se não for v1 reconhecido.

    Mapeamento v1 → v2 (NewSale → subscription.activated):

    | v1 (payload.event.X)        | v2 (payload.event.subscription.Y)               |
    |-----------------------------|-------------------------------------------------|
    | `transactionId`             | `id`                                            |
    | `paidAt`                    | `activatedAt`                                   |
    | `paymentMethod`             | `paymentMethod`                                 |
    | `totalAmount` (R$ float)    | `lastInvoice.amount.totalCents` (int em cents)  |
    | `userPhone`                 | `payer.phone`                                   |
    | `userEmail`                 | `payer.email`                                   |
    | `userName` ("First Last")   | `payer.firstName` + `payer.lastName`            |
    | `userDocument`              | `payer.document`                                |
    | `groupId`                   | `event.product.id`                              |
    | `groupName`                 | `event.product.name`                            |

    Status (`subscription.status`) varia conforme o evento:

    | v1 type        | status v2     |
    |----------------|---------------|
    | NewSale        | `active`      |
    | Renewal        | `active`      |
    | Canceled       | `canceled`    |
    | Expired        | `expired`     |
    | ChargedBack    | `chargeback`  |
    | Refund         | `refunded`    |
    | AbandonedCart  | `abandoned`   |
    """
    if not is_v1_payload(payload):
        return payload

    v1_type = str(payload.get("type", ""))
    v2_type = _V1_TO_V2_EVENT_MAP.get(v1_type)
    if v2_type is None:
        # v1 com type desconhecido — passa adiante e deixa o handler logar.
        return payload

    event = payload.get("event", {}) or {}

    # Split user name em first/last (best-effort)
    user_name = str(event.get("userName") or "").strip()
    if " " in user_name:
        first_name, last_name = user_name.split(" ", 1)
    else:
        first_name, last_name = user_name, ""

    # Converte totalAmount (R$ float) pra cents (int)
    total_amount = event.get("totalAmount")
    total_cents: int | None = None
    if total_amount is not None:
        try:
            total_cents = round(float(total_amount) * 100)
        except (TypeError, ValueError):
            total_cents = None

    status = _SUBSCRIPTION_STATUS_BY_V1_TYPE.get(v1_type, "unknown")

    return {
        "type": v2_type,
        "version": "1.0.0-normalized",
        "event": {
            "subscription": {
                "id": event.get("transactionId", ""),
                "activatedAt": event.get("paidAt", ""),
                "status": status,
                "paymentMethod": event.get("paymentMethod", ""),
                "payer": {
                    "phone": event.get("userPhone", ""),
                    "email": event.get("userEmail", ""),
                    "firstName": first_name,
                    "lastName": last_name,
                    "document": event.get("userDocument", ""),
                },
                "lastInvoice": {
                    "amount": {
                        "totalCents": total_cents,
                        "subtotalCents": total_cents,
                    },
                },
            },
            "product": {
                "id": event.get("groupId", ""),
                "name": event.get("groupName", ""),
            },
        },
    }


_SUBSCRIPTION_STATUS_BY_V1_TYPE: dict[str, str] = {
    "NewSale": "active",
    "Renewal": "active",
    "Canceled": "canceled",
    "Expired": "expired",
    "ChargedBack": "chargeback",
    "Refund": "refunded",
    "AbandonedCart": "abandoned",
}
