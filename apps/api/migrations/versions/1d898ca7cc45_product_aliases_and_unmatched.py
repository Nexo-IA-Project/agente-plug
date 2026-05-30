"""product aliases + lead.product_unmatched

Revision ID: 1d898ca7cc45
Revises: c2d3e4f5a6b7
Create Date: 2026-05-29

down_revision chosen from the single active head reported by
`alembic heads` at time of writing (c2d3e4f5a6b7).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "1d898ca7cc45"
down_revision = "c2d3e4f5a6b7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "product_hubla_aliases",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "account_id",
            UUID(as_uuid=True),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("hubla_id", sa.String(200), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.UniqueConstraint("account_id", "hubla_id", name="uq_product_alias_account_hubla"),
    )
    op.create_index(
        "ix_product_alias_account_hubla",
        "product_hubla_aliases",
        ["account_id", "hubla_id"],
    )
    op.create_index(
        "ix_product_alias_product",
        "product_hubla_aliases",
        ["product_id"],
    )
    op.add_column(
        "leads",
        sa.Column(
            "product_unmatched",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.create_index(
        "ix_leads_account_unmatched",
        "leads",
        ["account_id"],
        postgresql_where=sa.text("product_unmatched"),
    )


def downgrade() -> None:
    op.drop_index("ix_leads_account_unmatched", table_name="leads")
    op.drop_column("leads", "product_unmatched")
    op.drop_index("ix_product_alias_product", table_name="product_hubla_aliases")
    op.drop_index("ix_product_alias_account_hubla", table_name="product_hubla_aliases")
    op.drop_table("product_hubla_aliases")
