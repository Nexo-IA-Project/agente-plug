"""normalize hubla event_type names to match Hubla v2 official docs

Revision ID: f2e1d3c4b5a6
Revises: 10e0eb158b4d
Create Date: 2026-05-27 23:00:00.000000+00:00

Auditoria contra a doc oficial Hubla v2.0.0:
https://hubla.gitbook.io/docs/webhooks/eventos-v2

13 nomes no enum interno divergiam do que a Hubla realmente envia. Como
`onboarding_flows.trigger_event_type` referencia esses nomes, qualquer flow
configurado com um nome legado NUNCA dispara — porque o tipo nunca chega.

Esta migration:
- Atualiza `onboarding_flows.trigger_event_type` aplicando o mapa legado → correto.
- NÃO toca `hubla_events.event_type` (log imutável de payloads recebidos —
  preserva o que a Hubla efetivamente mandou, qualquer que seja).

Mapeamento (LEGACY → HUBLA v2 correto):
    lead.abandoned_cart                  → lead.abandoned_checkout
    member.access_granted                → customer.member_added
    member.access_removed                → customer.member_removed
    subscription.expired                 → subscription.expiring
    subscription.auto_renewal_disabled   → subscription.renewal_disabled
    subscription.auto_renewal_enabled    → subscription.renewal_enabled
    invoice.payment_completed            → invoice.payment_succeeded
    installment.created                  → smart_installment.created
    installment.failed                   → smart_installment.aborted
    installment.in_progress              → smart_installment.on_schedule
    installment.overdue                  → smart_installment.off_schedule
    installment.cancelled                → smart_installment.canceled
    installment.completed                → smart_installment.completed
    refund_request.cancelled             → refund_request.canceled
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

from alembic import op


revision: str = "f2e1d3c4b5a6"
down_revision: Union[str, None] = "10e0eb158b4d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_LEGACY_TO_CANONICAL: dict[str, str] = {
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


def upgrade() -> None:
    for old, new in _LEGACY_TO_CANONICAL.items():
        op.execute(
            f"""
            UPDATE onboarding_flows
            SET trigger_event_type = '{new}'
            WHERE trigger_event_type = '{old}';
            """
        )


def downgrade() -> None:
    for old, new in _LEGACY_TO_CANONICAL.items():
        op.execute(
            f"""
            UPDATE onboarding_flows
            SET trigger_event_type = '{old}'
            WHERE trigger_event_type = '{new}';
            """
        )
