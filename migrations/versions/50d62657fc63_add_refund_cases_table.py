"""add_refund_cases_table

Revision ID: 50d62657fc63
Revises: 995e17c86849
Create Date: 2026-04-24

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision: str = '50d62657fc63'
down_revision: Union[str, None] = '995e17c86849'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'refund_cases',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('contact_id', sa.String(), nullable=False),
        sa.Column('conversation_id', sa.String(), nullable=False),
        sa.Column('purchase_id', sa.String(), nullable=True),
        sa.Column('product_name', sa.String(), nullable=True),
        sa.Column('student_email', sa.String(), nullable=False),
        sa.Column('student_cpf', sa.String(), nullable=True),
        sa.Column('refund_reason', sa.String(), nullable=True),
        sa.Column('days_since_purchase', sa.Integer(), nullable=True),
        sa.Column('within_deadline', sa.Boolean(), nullable=True),
        sa.Column('is_duplicate_purchase', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('offers_made', JSONB(), nullable=False, server_default='[]'),
        sa.Column('offer_accepted', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('refund_processed_this_turn', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='collecting'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_refund_cases_account_contact', 'refund_cases', ['account_id', 'contact_id'])
    op.create_index(op.f('ix_refund_cases_account_id'), 'refund_cases', ['account_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_refund_cases_account_id'), table_name='refund_cases')
    op.drop_index('idx_refund_cases_account_contact', table_name='refund_cases')
    op.drop_table('refund_cases')
