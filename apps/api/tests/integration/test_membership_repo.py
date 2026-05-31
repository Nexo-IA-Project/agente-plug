from __future__ import annotations

import os
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.adapters.db.repositories.identity_repo import IdentityRepository
from shared.adapters.db.repositories.membership_repo import MembershipRepository
from shared.domain.entities.identity import Identity
from shared.domain.entities.membership import Membership
from shared.domain.entities.user import UserRole


@pytest.fixture(scope="session", autouse=True)
def _apply_migrations(database_url: str) -> None:
    """Aplica alembic migrations no testcontainer Postgres uma vez por sessão."""
    from shared.config.settings import get_settings

    original = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = database_url
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


ACC1 = UUID("44444444-4444-4444-4444-444444444444")
ACC2 = UUID("55555555-5555-5555-5555-555555555555")


@pytest.fixture(autouse=True)
async def _setup(db_session: AsyncSession) -> None:
    await db_session.execute(text("DELETE FROM memberships"))
    await db_session.execute(text("DELETE FROM identities"))
    for acc, name in ((ACC1, "C1"), (ACC2, "C2")):
        await db_session.execute(
            text(
                "INSERT INTO accounts (id, name, settings, created_at) VALUES (:id, :n, '{}'::jsonb, NOW()) ON CONFLICT (id) DO NOTHING"
            ),
            {"id": str(acc), "n": name},
        )
    await db_session.commit()


@pytest.mark.asyncio
async def test_list_active_by_identity_spans_accounts(db_session: AsyncSession) -> None:
    ident = Identity(email="multi@x.com", password_hash="h", name="Multi")
    await IdentityRepository(db_session).save(ident)
    repo = MembershipRepository(db_session)
    await repo.save(Membership(identity_id=ident.id, account_id=ACC1, role=UserRole.OPERATOR))
    await repo.save(
        Membership(identity_id=ident.id, account_id=ACC2, role=UserRole.ADMIN, is_owner=True)
    )
    await db_session.commit()
    views = await repo.list_active_by_identity(ident.id)
    assert {v.account_id for v in views} == {ACC1, ACC2}
    owner_view = next(v for v in views if v.account_id == ACC2)
    assert owner_view.is_owner is True
    assert owner_view.account_name == "C2"


@pytest.mark.asyncio
async def test_get_by_identity_and_account(db_session: AsyncSession) -> None:
    ident = Identity(email="x@x.com", password_hash="h", name="X")
    await IdentityRepository(db_session).save(ident)
    repo = MembershipRepository(db_session)
    await repo.save(Membership(identity_id=ident.id, account_id=ACC1, role=UserRole.OPERATOR))
    await db_session.commit()
    m = await repo.get_by_identity_and_account(ident.id, ACC1)
    assert m is not None and m.role == UserRole.OPERATOR
    assert await repo.get_by_identity_and_account(ident.id, ACC2) is None


@pytest.mark.asyncio
async def test_count_active_admins(db_session: AsyncSession) -> None:
    ir = IdentityRepository(db_session)
    repo = MembershipRepository(db_session)
    for i, role in enumerate([UserRole.ADMIN, UserRole.ADMIN, UserRole.OPERATOR]):
        ident = Identity(email=f"a{i}@x.com", password_hash="h", name=f"A{i}")
        await ir.save(ident)
        await repo.save(Membership(identity_id=ident.id, account_id=ACC1, role=role))
    await db_session.commit()
    assert await repo.count_active_admins(ACC1) == 2
