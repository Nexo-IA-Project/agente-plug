"""create hubla_events and leads tables

Revision ID: 83ff9745e1a6
Revises: 2c5504aac687
Create Date: 2026-05-22
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "83ff9745e1a6"
down_revision = "2c5504aac687"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hubla_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("account_id", sa.UUID(), nullable=False),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("hubla_subscription_id", sa.String(100), nullable=False),
        sa.Column("hubla_product_id", sa.String(100), nullable=False, server_default=""),
        sa.Column("product_name", sa.String(300), nullable=False, server_default=""),
        sa.Column("payer_phone", sa.String(30), nullable=False, server_default=""),
        sa.Column("payer_email", sa.String(200), nullable=False, server_default=""),
        sa.Column("payer_name", sa.String(200), nullable=False, server_default=""),
        sa.Column("contact_id", sa.UUID(), nullable=True),
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_hubla_events_account_type", "hubla_events", ["account_id", "event_type"])
    op.create_index(
        "ix_hubla_events_subscription",
        "hubla_events",
        ["account_id", "hubla_subscription_id"],
    )

    op.create_table(
        "leads",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("account_id", sa.UUID(), nullable=False),
        sa.Column("hubla_subscription_id", sa.String(100), nullable=False),
        sa.Column("contact_id", sa.UUID(), nullable=True),
        sa.Column("payer_phone", sa.String(30), nullable=False, server_default=""),
        sa.Column("payer_name", sa.String(200), nullable=False, server_default=""),
        sa.Column("payer_email", sa.String(200), nullable=False, server_default=""),
        sa.Column("payer_document", sa.String(20), nullable=True),
        sa.Column("hubla_product_id", sa.String(100), nullable=False, server_default=""),
        sa.Column("product_name", sa.String(300), nullable=False, server_default=""),
        sa.Column("offer_id", sa.String(100), nullable=True),
        sa.Column("offer_name", sa.String(300), nullable=True),
        sa.Column("amount_total_cents", sa.Integer(), nullable=True),
        sa.Column("amount_subtotal_cents", sa.Integer(), nullable=True),
        sa.Column("payment_method", sa.String(50), nullable=True),
        sa.Column("subscription_status", sa.String(30), nullable=False, server_default="unknown"),
        sa.Column("utm_source", sa.String(200), nullable=True),
        sa.Column("utm_medium", sa.String(200), nullable=True),
        sa.Column("utm_campaign", sa.String(500), nullable=True),
        sa.Column("utm_content", sa.String(500), nullable=True),
        sa.Column("utm_term", sa.String(200), nullable=True),
        sa.Column("session_ip", sa.String(50), nullable=True),
        sa.Column("session_url", sa.Text(), nullable=True),
        sa.Column("fbp", sa.String(100), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_event_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_event_type", sa.String(80), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "account_id", "hubla_subscription_id", name="uq_leads_account_subscription"
        ),
    )
    op.create_index("ix_leads_account_phone", "leads", ["account_id", "payer_phone"])
    op.create_index("ix_leads_account_status", "leads", ["account_id", "subscription_status"])
    op.create_index("ix_leads_account_activated", "leads", ["account_id", "activated_at"])


def downgrade() -> None:
    op.drop_index("ix_leads_account_activated", table_name="leads")
    op.drop_index("ix_leads_account_status", table_name="leads")
    op.drop_index("ix_leads_account_phone", table_name="leads")
    op.drop_table("leads")
    op.drop_index("ix_hubla_events_subscription", table_name="hubla_events")
    op.drop_index("ix_hubla_events_account_type", table_name="hubla_events")
    op.drop_table("hubla_events")
