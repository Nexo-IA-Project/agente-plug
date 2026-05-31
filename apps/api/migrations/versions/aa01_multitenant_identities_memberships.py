"""multitenant: identities + memberships + backfill

Revision ID: aa01mt
Revises: a9b0c1d2e3f4
Create Date: 2026-05-31
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "aa01mt"
down_revision: str | Sequence[str] = "a9b0c1d2e3f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("accounts", sa.Column("legal_name", sa.String(200), nullable=True))
    op.add_column("accounts", sa.Column("tax_id", sa.String(40), nullable=True))
    op.add_column("accounts", sa.Column("contact_email", sa.String(200), nullable=True))
    op.add_column("accounts", sa.Column("contact_phone", sa.String(40), nullable=True))

    op.create_table(
        "identities",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(200), nullable=False),
        sa.Column("password_hash", sa.String(200), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("avatar", sa.LargeBinary, nullable=True),
        sa.Column(
            "must_change_password",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("TRUE"),
        ),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("TRUE")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("email", name="uq_identities_email"),
    )
    op.create_table(
        "memberships",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "identity_id",
            sa.String(36),
            sa.ForeignKey("identities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "account_id",
            UUID(as_uuid=True),
            sa.ForeignKey("accounts.id"),
            nullable=False,
        ),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column(
            "profile_id",
            UUID(as_uuid=True),
            sa.ForeignKey("profiles.id"),
            nullable=True,
        ),
        sa.Column("is_owner", sa.Boolean, nullable=False, server_default=sa.text("FALSE")),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("TRUE")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.UniqueConstraint("identity_id", "account_id", name="uq_membership_identity_account"),
    )
    op.create_index("ix_memberships_account_id", "memberships", ["account_id"])
    op.create_index("ix_memberships_identity_id", "memberships", ["identity_id"])
    op.create_index(
        "uq_membership_owner_per_account",
        "memberships",
        ["account_id"],
        unique=True,
        postgresql_where=sa.text("is_owner"),
    )

    conn = op.get_bind()

    dup = conn.execute(
        sa.text("SELECT lower(email) FROM users GROUP BY lower(email) HAVING count(*) > 1 LIMIT 1")
    ).first()
    if dup is not None:
        raise RuntimeError(f"Backfill abortado: e-mail duplicado entre contas em users: {dup[0]!r}")

    conn.execute(
        sa.text(
            """
            INSERT INTO identities (id, email, password_hash, name, avatar, must_change_password, is_active, created_at, last_login_at)
            SELECT DISTINCT ON (lower(u.email)) u.id, u.email, u.password_hash, u.name, u.avatar, u.must_change_password, u.is_active, u.created_at, u.last_login_at
            FROM users u ORDER BY lower(u.email), u.created_at ASC
            """
        )
    )
    conn.execute(
        sa.text(
            """
            INSERT INTO memberships (id, identity_id, account_id, role, profile_id, is_owner, is_active, created_at)
            SELECT gen_random_uuid()::text, i.id, u.account_id, u.role, u.profile_id, FALSE, u.is_active, u.created_at
            FROM users u JOIN identities i ON lower(i.email) = lower(u.email)
            """
        )
    )
    conn.execute(
        sa.text(
            """
            UPDATE memberships SET is_owner = TRUE WHERE id IN (
                SELECT DISTINCT ON (account_id) id FROM memberships WHERE role = 'admin' ORDER BY account_id, created_at ASC
            )
            """
        )
    )
    conn.execute(
        sa.text(
            """
            UPDATE memberships SET is_owner = TRUE, role = 'admin' WHERE id IN (
                SELECT DISTINCT ON (account_id) id FROM memberships
                WHERE account_id NOT IN (SELECT account_id FROM memberships WHERE is_owner)
                ORDER BY account_id, created_at ASC
            )
            """
        )
    )
    conn.execute(sa.text("UPDATE accounts SET legal_name = '(pendente)' WHERE legal_name IS NULL"))

    n_users = conn.execute(sa.text("SELECT count(*) FROM users")).scalar()
    n_emails = conn.execute(sa.text("SELECT count(DISTINCT lower(email)) FROM users")).scalar()
    n_ident = conn.execute(sa.text("SELECT count(*) FROM identities")).scalar()
    n_memb = conn.execute(sa.text("SELECT count(*) FROM memberships")).scalar()
    assert n_ident == n_emails, f"identities={n_ident} != distinct emails={n_emails}"
    assert n_memb == n_users, f"memberships={n_memb} != users={n_users}"
    orphans = conn.execute(
        sa.text(
            """
            SELECT count(*) FROM users u
            LEFT JOIN memberships m ON m.account_id = u.account_id
              AND m.identity_id = (SELECT id FROM identities i WHERE lower(i.email) = lower(u.email))
            WHERE m.id IS NULL
            """
        )
    ).scalar()
    assert orphans == 0, f"{orphans} linhas de users sem membership"
    bad_owner = conn.execute(
        sa.text(
            """
            SELECT count(*) FROM (
                SELECT account_id FROM memberships GROUP BY account_id HAVING count(*) FILTER (WHERE is_owner) <> 1
            ) x
            """
        )
    ).scalar()
    assert bad_owner == 0, f"{bad_owner} contas sem exatamente 1 owner"
    null_pw = conn.execute(
        sa.text("SELECT count(*) FROM identities WHERE password_hash IS NULL OR password_hash = ''")
    ).scalar()
    assert null_pw == 0, f"{null_pw} identities com password_hash vazio"


def downgrade() -> None:
    op.drop_index("uq_membership_owner_per_account", table_name="memberships")
    op.drop_index("ix_memberships_identity_id", table_name="memberships")
    op.drop_index("ix_memberships_account_id", table_name="memberships")
    op.drop_table("memberships")
    op.drop_table("identities")
    op.drop_column("accounts", "contact_phone")
    op.drop_column("accounts", "contact_email")
    op.drop_column("accounts", "tax_id")
    op.drop_column("accounts", "legal_name")
