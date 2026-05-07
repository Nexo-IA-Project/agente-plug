"""fix: followup_enrollments.conversation_id — UUID FK → VARCHAR

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
Create Date: 2026-05-07 00:00:00.000000

O campo conversation_id armazena o ID externo do ChatNexo (string), não
um UUID interno. Remove o FK para conversations.id e muda para VARCHAR.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "b3c4d5e6f7a8"
down_revision = "a2b3c4d5e6f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "followup_enrollments_conversation_id_fkey",
        "followup_enrollments",
        type_="foreignkey",
    )
    op.alter_column(
        "followup_enrollments",
        "conversation_id",
        existing_type=sa.dialects.postgresql.UUID(as_uuid=True),
        type_=sa.String(200),
        postgresql_using="conversation_id::text",
    )


def downgrade() -> None:
    op.alter_column(
        "followup_enrollments",
        "conversation_id",
        existing_type=sa.String(200),
        type_=sa.dialects.postgresql.UUID(as_uuid=True),
        postgresql_using="conversation_id::uuid",
    )
    op.create_foreign_key(
        "followup_enrollments_conversation_id_fkey",
        "followup_enrollments",
        "conversations",
        ["conversation_id"],
        ["id"],
    )
