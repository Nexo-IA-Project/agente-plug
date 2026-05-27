"""Eventos Hubla v2 — catálogo oficial dos 25 tipos."""

from __future__ import annotations

from typing import Literal, get_args

HublaEventType = Literal[
    # Lead (1)
    "lead.abandoned_cart",
    # Member (2)
    "member.access_granted",
    "member.access_removed",
    # Subscription (6)
    "subscription.created",
    "subscription.activated",
    "subscription.expired",
    "subscription.deactivated",
    "subscription.auto_renewal_disabled",
    "subscription.auto_renewal_enabled",
    # Invoice (6)
    "invoice.created",
    "invoice.status_updated",
    "invoice.payment_completed",
    "invoice.payment_failed",
    "invoice.expired",
    "invoice.refunded",
    # Installment (6)
    "installment.created",
    "installment.failed",
    "installment.in_progress",
    "installment.overdue",
    "installment.cancelled",
    "installment.completed",
    # Refund Request (4)
    "refund_request.created",
    "refund_request.accepted",
    "refund_request.cancelled",
    "refund_request.rejected",
]

ALL_HUBLA_EVENT_TYPES: frozenset[str] = frozenset(get_args(HublaEventType))

PURCHASE_EVENT_TYPES: frozenset[str] = frozenset({"subscription.activated"})
"""Eventos que disparam o pipeline legado de PurchaseHandler (welcome + access_case)."""


def is_valid_hubla_event_type(value: str) -> bool:
    return value in ALL_HUBLA_EVENT_TYPES
