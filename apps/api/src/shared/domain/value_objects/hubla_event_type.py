"""Eventos Hubla v2 — catálogo oficial dos 25 tipos.

Identificadores técnicos baseados na doc oficial:
https://hubla.gitbook.io/docs/webhooks/eventos-v2

Mapeamento por seção (Lead / Membro / Assinatura / Fatura / Parcelamento
Inteligente / Solicitação de Reembolso). Os 25 nomes a seguir são o `payload.type`
exato que a Hubla envia — qualquer divergência aqui causa o evento a ser dropado
pelo `HublaEventHandler`.
"""

from __future__ import annotations

from typing import Literal, get_args

HublaEventType = Literal[
    # Lead (1)
    "lead.abandoned_checkout",
    # Membro (2)
    "customer.member_added",
    "customer.member_removed",
    # Assinatura (6)
    "subscription.created",
    "subscription.activated",
    "subscription.expiring",
    "subscription.deactivated",
    "subscription.renewal_disabled",
    "subscription.renewal_enabled",
    # Fatura (6)
    "invoice.created",
    "invoice.status_updated",
    "invoice.payment_succeeded",
    "invoice.payment_failed",
    "invoice.expired",
    "invoice.refunded",
    # Parcelamento Inteligente (6)
    "smart_installment.created",
    "smart_installment.aborted",
    "smart_installment.on_schedule",
    "smart_installment.off_schedule",
    "smart_installment.canceled",
    "smart_installment.completed",
    # Solicitação de Reembolso (4)
    "refund_request.created",
    "refund_request.accepted",
    "refund_request.canceled",
    "refund_request.rejected",
]

ALL_HUBLA_EVENT_TYPES: frozenset[str] = frozenset(get_args(HublaEventType))

PURCHASE_EVENT_TYPES: frozenset[str] = frozenset({"subscription.activated"})
"""Eventos que disparam o pipeline legado de PurchaseHandler (welcome + access_case)."""


# Mapa de nomes antigos (errados, usados em código/dados anteriores) → nomes
# corretos da Hubla. Usado pela função `normalize_event_type` em runtime
# (defesa em profundidade) E como referência pra migration de dados que
# atualiza `onboarding_flows.trigger_event_type`.
LEGACY_EVENT_TYPE_MAP: dict[str, str] = {
    "lead.abandoned_cart": "lead.abandoned_checkout",
    "member.access_granted": "customer.member_added",
    "member.access_removed": "customer.member_removed",
    "subscription.expired": "subscription.expiring",
    "subscription.auto_renewal_disabled": "subscription.renewal_disabled",
    "subscription.auto_renewal_enabled": "subscription.renewal_enabled",
    "invoice.payment_completed": "invoice.payment_succeeded",
    "installment.created": "smart_installment.created",
    "installment.failed": "smart_installment.aborted",
    "installment.in_progress": "smart_installment.on_schedule",
    "installment.overdue": "smart_installment.off_schedule",
    "installment.cancelled": "smart_installment.canceled",
    "installment.completed": "smart_installment.completed",
    "refund_request.cancelled": "refund_request.canceled",
}


def is_valid_hubla_event_type(value: str) -> bool:
    return value in ALL_HUBLA_EVENT_TYPES


def normalize_event_type(value: str) -> str:
    """Retorna o nome canônico Hubla v2 a partir de qualquer apelido legado.

    Se `value` já é um tipo válido, retorna inalterado. Se for um nome legado
    do enum antigo (ex: `member.access_granted`), retorna o equivalente correto
    (`customer.member_added`). Tipos completamente desconhecidos passam adiante
    inalterados para o handler logar como `hubla_unknown_event`.
    """
    return LEGACY_EVENT_TYPE_MAP.get(value, value)
