"""rename courses to products

Revision ID: 42c2b623d919
Revises: c1d2e3f4a5b6
Create Date: 2026-05-22

"""
from __future__ import annotations

from alembic import op

revision = "42c2b623d919"
down_revision = "c1d2e3f4a5b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Renomeia constraint única e index antes de renomear a tabela
    op.execute(
        "ALTER TABLE courses RENAME CONSTRAINT uq_courses_account_hubla TO uq_products_account_hubla"
    )
    op.execute("ALTER INDEX ix_courses_account_id RENAME TO ix_products_account_id")

    # Renomeia a tabela
    op.rename_table("courses", "products")

    # Renomeia a coluna FK e index em followup_flows
    op.execute("ALTER TABLE followup_flows RENAME COLUMN course_id TO product_id")
    op.execute("ALTER INDEX ix_followup_flows_course_id RENAME TO ix_followup_flows_product_id")

    # Renomeia a FK constraint (nome real encontrado no DB: fk_followup_flows_course_id)
    op.execute("""
        ALTER TABLE followup_flows
        DROP CONSTRAINT IF EXISTS fk_followup_flows_course_id
    """)
    op.execute("""
        ALTER TABLE followup_flows
        ADD CONSTRAINT fk_followup_flows_product_id
        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT
    """)


def downgrade() -> None:
    # Drop FK atual (referencia products.id via product_id)
    op.execute("""
        ALTER TABLE followup_flows
        DROP CONSTRAINT IF EXISTS fk_followup_flows_product_id
    """)
    # Reverte index e coluna em followup_flows
    op.execute("ALTER INDEX ix_followup_flows_product_id RENAME TO ix_followup_flows_course_id")
    op.execute("ALTER TABLE followup_flows RENAME COLUMN product_id TO course_id")
    # Reverte tabela
    op.rename_table("products", "courses")
    # Reverte index e constraint que agora estão na tabela courses
    op.execute("ALTER INDEX ix_products_account_id RENAME TO ix_courses_account_id")
    op.execute(
        "ALTER TABLE courses RENAME CONSTRAINT uq_products_account_hubla TO uq_courses_account_hubla"
    )
    # Recria FK com nomes antigos
    op.execute("""
        ALTER TABLE followup_flows
        ADD CONSTRAINT fk_followup_flows_course_id
        FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE RESTRICT
    """)
