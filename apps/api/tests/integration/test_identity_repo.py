from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.adapters.db.repositories.identity_repo import IdentityRepository
from shared.domain.entities.identity import Identity


@pytest.fixture(scope="session", autouse=True)
def _apply_migrations(database_url: str) -> None:
    """Aplica alembic migrations no testcontainer Postgres uma vez por sessão."""
    import os

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


@pytest.fixture(autouse=True)
async def _clean(db_session: AsyncSession) -> None:
    await db_session.execute(text("DELETE FROM memberships"))
    await db_session.execute(text("DELETE FROM identities"))
    await db_session.commit()


@pytest.mark.asyncio
async def test_save_and_get_by_email_global(db_session: AsyncSession) -> None:
    repo = IdentityRepository(db_session)
    await repo.save(Identity(email="z@x.com", password_hash="h", name="Zoe"))
    await db_session.commit()
    loaded = await repo.get_by_email("z@x.com")
    assert loaded is not None and loaded.name == "Zoe"
    assert await repo.get_by_email("Z@X.COM") is not None  # case-insensitive


@pytest.mark.asyncio
async def test_update_password_sets_flag(db_session: AsyncSession) -> None:
    repo = IdentityRepository(db_session)
    ident = Identity(email="p@x.com", password_hash="old", name="P", must_change_password=False)
    await repo.save(ident)
    await db_session.commit()
    await repo.update_password(ident.id, "new", must_change_password=True)
    await db_session.commit()
    reloaded = await repo.get_by_id(ident.id)
    assert reloaded is not None
    assert reloaded.password_hash == "new"
    assert reloaded.must_change_password is True
