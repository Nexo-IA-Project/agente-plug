"""enable_pgvector

Revision ID: aae1836f9176
Revises: c3f1a82e9d74
Create Date: 2026-04-25

"""
from collections.abc import Sequence

from alembic import op

revision: str = 'aae1836f9176'
down_revision: str | None = 'c3f1a82e9d74'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS vector;")
