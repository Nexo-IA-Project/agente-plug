"""meta template media table

Revision ID: 10e0eb158b4d
Revises: 9f07c98d5b22
Create Date: 2026-05-27

Cria tabela meta_template_media (BYTEA + dedup por sha256) para armazenar
mídia de templates Meta no nosso Postgres em vez de R2 externo.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "10e0eb158b4d"
down_revision = "9f07c98d5b22"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "meta_template_media",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("mime", sa.String(128), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("account_id", "sha256", name="uq_meta_template_media_account_sha"),
        sa.CheckConstraint(
            "kind IN ('IMAGE', 'VIDEO', 'DOCUMENT')",
            name="ck_meta_template_media_kind",
        ),
    )


def downgrade() -> None:
    op.drop_table("meta_template_media")
