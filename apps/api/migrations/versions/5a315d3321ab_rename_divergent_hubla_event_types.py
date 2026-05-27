"""rename divergent hubla event types

Revision ID: 5a315d3321ab
Revises: 3e4f5a6b7c8d
Create Date: 2026-05-27 04:41:12.002033+00:00

Renomeia trigger_event_type em onboarding_flows para alinhar com a Hubla v2:
- lead.abandoned        -> lead.abandoned_cart
- subscription.expiring -> subscription.expired

NAO toca hubla_events.event_type (log imutavel - historico preservado).

Obs: a tabela followup_flows foi renomeada para onboarding_flows na migration
8bdd77da3217. Esta migration opera sobre o nome atual (onboarding_flows).
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "5a315d3321ab"
down_revision: Union[str, None] = "3e4f5a6b7c8d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE onboarding_flows
        SET trigger_event_type = 'lead.abandoned_cart'
        WHERE trigger_event_type = 'lead.abandoned';
        """
    )
    op.execute(
        """
        UPDATE onboarding_flows
        SET trigger_event_type = 'subscription.expired'
        WHERE trigger_event_type = 'subscription.expiring';
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE onboarding_flows
        SET trigger_event_type = 'lead.abandoned'
        WHERE trigger_event_type = 'lead.abandoned_cart';
        """
    )
    op.execute(
        """
        UPDATE onboarding_flows
        SET trigger_event_type = 'subscription.expiring'
        WHERE trigger_event_type = 'subscription.expired';
        """
    )
