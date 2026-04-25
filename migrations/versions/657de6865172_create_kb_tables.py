"""create_kb_tables

Revision ID: 657de6865172
Revises: aae1836f9176
Create Date: 2026-04-25

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB

revision: str = '657de6865172'
down_revision: str | None = 'aae1836f9176'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'knowledge_documents',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('filename', sa.String(500), nullable=False),
        sa.Column('mime_type', sa.String(100), nullable=False),
        sa.Column('file_size_bytes', sa.BigInteger(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('chunk_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('tags', JSONB(), nullable=False, server_default='[]'),
        sa.Column('error_message', sa.String(), nullable=True),
        sa.Column('created_by', sa.String(100), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
    )
    op.create_index('idx_knowledge_documents_account', 'knowledge_documents', ['account_id'])

    op.create_table(
        'knowledge_chunks',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('document_id', sa.String(36), nullable=False),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('text', sa.String(), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('token_count', sa.Integer(), nullable=False),
        sa.Column('embedding', Vector(1536), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
    )
    op.create_index('idx_knowledge_chunks_document', 'knowledge_chunks', ['document_id'])
    op.create_index('idx_knowledge_chunks_account', 'knowledge_chunks', ['account_id'])

    op.create_table(
        'kb_usage_logs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('query', sa.String(), nullable=False),
        sa.Column('result_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
    )
    op.create_index('idx_kb_usage_logs_account', 'kb_usage_logs', ['account_id'])

    op.create_table(
        'admin_users',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(200), nullable=False),
        sa.Column('password_hash', sa.String(200), nullable=False),
        sa.Column('role', sa.String(20), nullable=False, server_default='viewer'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.UniqueConstraint('account_id', 'email', name='uq_admin_users_account_email'),
    )


def downgrade() -> None:
    op.drop_table('admin_users')
    op.drop_index('idx_kb_usage_logs_account', table_name='kb_usage_logs')
    op.drop_table('kb_usage_logs')
    op.drop_index('idx_knowledge_chunks_account', table_name='knowledge_chunks')
    op.drop_index('idx_knowledge_chunks_document', table_name='knowledge_chunks')
    op.drop_table('knowledge_chunks')
    op.drop_index('idx_knowledge_documents_account', table_name='knowledge_documents')
    op.drop_table('knowledge_documents')
