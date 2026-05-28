"""create users and smtp_config tables, migrate admin_users

Revision ID: b1c2d3e4f5a6
Revises: (f2e1d3c4b5a6, a1b2c3d4e5f6)
Create Date: 2026-05-28

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision = "b1c2d3e4f5a6"
down_revision: Union[str, Sequence[str]] = ("f2e1d3c4b5a6", "a1b2c3d4e5f6")
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("account_id", sa.Integer, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("email", sa.String(200), nullable=False),
        sa.Column("password_hash", sa.String(200), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("avatar", sa.LargeBinary, nullable=True),
        sa.Column("must_change_password", sa.Boolean, nullable=False, server_default=sa.text("TRUE")),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("TRUE")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("account_id", "email", name="uq_users_account_email"),
    )
    op.create_index("ix_users_account_id", "users", ["account_id"])

    op.create_table(
        "smtp_config",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("account_id", sa.Integer, nullable=False, unique=True),
        sa.Column("host", sa.String(200), nullable=False),
        sa.Column("port", sa.Integer, nullable=False),
        sa.Column("username", sa.String(200), nullable=False),
        sa.Column("encrypted_password", sa.Text, nullable=False),
        sa.Column("use_tls", sa.Boolean, nullable=False, server_default=sa.text("TRUE")),
        sa.Column("from_name", sa.String(100), nullable=False),
        sa.Column("from_email", sa.String(200), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )

    # Migra admin_users → users
    # role fixo 'admin' (descarta 'viewer'/'editor' existentes — todos eram admins de fato)
    # name = parte local do email (antes do @)
    # must_change_password = FALSE para usuários já existentes
    op.execute(
        """
        INSERT INTO users (id, account_id, name, email, password_hash, role,
                           must_change_password, is_active, created_at)
        SELECT id,
               account_id,
               SPLIT_PART(email, '@', 1),
               email,
               password_hash,
               'admin',
               FALSE,
               TRUE,
               created_at
        FROM admin_users
        """
    )

    op.drop_table("admin_users")


def downgrade() -> None:
    op.create_table(
        "admin_users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("account_id", sa.Integer, nullable=False),
        sa.Column("email", sa.String(200), nullable=False),
        sa.Column("password_hash", sa.String(200), nullable=False),
        sa.Column("role", sa.String(20), nullable=False, server_default="viewer"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("account_id", "email", name="uq_admin_users_account_email"),
    )
    op.execute(
        """
        INSERT INTO admin_users (id, account_id, email, password_hash, role, created_at)
        SELECT id, account_id, email, password_hash, role, created_at FROM users
        """
    )
    op.drop_index("ix_users_account_id", table_name="users")
    op.drop_table("smtp_config")
    op.drop_table("users")
