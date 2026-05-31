# tests/integration/test_multitenant_migration.py
"""Integration test: backfill da migração aa01mt (identities + memberships).

Insere 2 users (1 admin mais antigo + 1 operator), reproduz os passos de backfill
e valida contagens + owner = admin mais antigo. O schema do testcontainer é criado
por `_apply_migrations` (alembic upgrade heads), igual aos demais testes de migração.
"""

from __future__ import annotations

import os
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

ACC = UUID("33333333-3333-3333-3333-333333333333")


@pytest.fixture(scope="session", autouse=True)
def _apply_migrations(database_url: str) -> None:
    original = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = database_url

    from shared.config.settings import get_settings

    get_settings.cache_clear()  # type: ignore[attr-defined]
    try:
        from alembic import command
        from alembic.config import Config as AlembicConfig

        cfg = AlembicConfig("alembic.ini")
        cfg.set_main_option("sqlalchemy.url", database_url)
        command.upgrade(cfg, "heads")
    finally:
        if original is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = original
        get_settings.cache_clear()  # type: ignore[attr-defined]


@pytest.fixture(autouse=True)
async def _seed_users(db_session: AsyncSession) -> None:
    await db_session.execute(text("DELETE FROM memberships"))
    await db_session.execute(text("DELETE FROM identities"))
    await db_session.execute(text("DELETE FROM users"))
    await db_session.execute(
        text(
            "INSERT INTO accounts (id, name, settings, created_at) "
            "VALUES (:id, 'BackfillCo', '{}'::jsonb, NOW()) ON CONFLICT (id) DO NOTHING"
        ),
        {"id": str(ACC)},
    )
    await db_session.execute(
        text(
            "INSERT INTO users (id, account_id, name, email, password_hash, role, must_change_password, is_active, created_at) VALUES "
            "('11111111-0000-0000-0000-000000000001', :acc, 'Boss', 'boss@x.com', 'h1', 'admin', false, true, NOW() - interval '2 day'),"
            "('11111111-0000-0000-0000-000000000002', :acc, 'Emp', 'emp@x.com', 'h2', 'operator', false, true, NOW())"
        ),
        {"acc": str(ACC)},
    )
    await db_session.commit()


async def _run_backfill(session: AsyncSession) -> None:
    await session.execute(
        text(
            "INSERT INTO identities (id, email, password_hash, name, avatar, must_change_password, is_active, created_at, last_login_at) "
            "SELECT DISTINCT ON (lower(u.email)) u.id, u.email, u.password_hash, u.name, u.avatar, u.must_change_password, u.is_active, u.created_at, u.last_login_at "
            "FROM users u ORDER BY lower(u.email), u.created_at ASC"
        )
    )
    await session.execute(
        text(
            "INSERT INTO memberships (id, identity_id, account_id, role, profile_id, is_owner, is_active, created_at) "
            "SELECT gen_random_uuid()::text, i.id, u.account_id, u.role, u.profile_id, FALSE, u.is_active, u.created_at "
            "FROM users u JOIN identities i ON lower(i.email)=lower(u.email)"
        )
    )
    await session.execute(
        text(
            "UPDATE memberships SET is_owner=TRUE WHERE id IN ("
            "SELECT DISTINCT ON (account_id) id FROM memberships WHERE role='admin' ORDER BY account_id, created_at ASC)"
        )
    )
    await session.commit()


@pytest.mark.asyncio
async def test_backfill_creates_identities_and_memberships(db_session: AsyncSession) -> None:
    await _run_backfill(db_session)
    n_ident = (await db_session.execute(text("SELECT count(*) FROM identities"))).scalar()
    n_memb = (await db_session.execute(text("SELECT count(*) FROM memberships"))).scalar()
    assert n_ident == 2
    assert n_memb == 2
    owner_email = (
        await db_session.execute(
            text(
                "SELECT i.email FROM memberships m JOIN identities i ON i.id=m.identity_id "
                "WHERE m.is_owner AND m.account_id=:acc"
            ),
            {"acc": str(ACC)},
        )
    ).scalar()
    assert owner_email == "boss@x.com"
    n_owners = (
        await db_session.execute(
            text("SELECT count(*) FROM memberships WHERE is_owner AND account_id=:acc"),
            {"acc": str(ACC)},
        )
    ).scalar()
    assert n_owners == 1
