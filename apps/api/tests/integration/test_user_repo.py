from __future__ import annotations

from uuid import UUID

import pytest
from sqlalchemy import delete, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from shared.adapters.db.models import UserModel
from shared.adapters.db.repositories.user_repo import UserRepository
from shared.domain.entities.user import User, UserRole

# account_id agora é UUID com FK -> accounts. Usamos duas contas reais.
ACC1 = UUID("11111111-1111-1111-1111-111111111111")
ACC2 = UUID("22222222-2222-2222-2222-222222222222")


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
async def _clean_users(db_session: AsyncSession) -> None:
    """Garante contas e limpa a tabela users antes de cada teste."""
    await db_session.execute(delete(UserModel))
    for acc in (ACC1, ACC2):
        await db_session.execute(
            text(
                "INSERT INTO accounts (id, name, settings, created_at) "
                "VALUES (:id, :name, '{}'::jsonb, NOW()) ON CONFLICT (id) DO NOTHING"
            ),
            {"id": str(acc), "name": f"acc-{acc}"},
        )
    await db_session.commit()


@pytest.mark.asyncio
async def test_save_and_get_by_email(db_session: AsyncSession) -> None:
    repo = UserRepository(db_session)
    user = User(
        account_id=ACC1,
        name="Alice",
        email="alice@example.com",
        password_hash="hash1",
        role=UserRole.OPERATOR,
    )
    await repo.save(user)
    await db_session.commit()

    loaded = await repo.get_by_email(account_id=ACC1, email="alice@example.com")
    assert loaded is not None
    assert loaded.name == "Alice"
    assert loaded.role == UserRole.OPERATOR
    assert loaded.must_change_password is True


@pytest.mark.asyncio
async def test_get_by_id(db_session: AsyncSession) -> None:
    repo = UserRepository(db_session)
    user = User(
        account_id=ACC1,
        name="Bob",
        email="bob@example.com",
        password_hash="h",
        role=UserRole.ADMIN,
    )
    await repo.save(user)
    await db_session.commit()
    uid = user.id

    loaded = await repo.get_by_id(uid)
    assert loaded is not None
    assert loaded.email == "bob@example.com"


@pytest.mark.asyncio
async def test_list_by_account(db_session: AsyncSession) -> None:
    repo = UserRepository(db_session)
    for i in range(3):
        await repo.save(
            User(
                account_id=ACC1,
                name=f"User{i}",
                email=f"u{i}@x.com",
                password_hash="h",
                role=UserRole.ADMIN,
            )
        )
    await db_session.commit()

    users, total = await repo.list_by_account(account_id=ACC1, page=1, page_size=10)
    assert total >= 3
    assert len(users) >= 3


@pytest.mark.asyncio
async def test_update_password_and_clear_flag(db_session: AsyncSession) -> None:
    repo = UserRepository(db_session)
    u = User(
        account_id=ACC1,
        name="X",
        email="x@x.com",
        password_hash="old",
        role=UserRole.ADMIN,
        must_change_password=True,
    )
    await repo.save(u)
    await db_session.commit()
    uid = u.id

    await repo.update_password(user_id=uid, new_hash="new", must_change_password=False)
    await db_session.commit()

    loaded = await repo.get_by_id(uid)
    assert loaded is not None
    assert loaded.password_hash == "new"
    assert loaded.must_change_password is False


@pytest.mark.asyncio
async def test_unique_email_per_account(db_session: AsyncSession) -> None:
    repo = UserRepository(db_session)
    await repo.save(
        User(
            account_id=ACC1,
            name="A",
            email="dup@x.com",
            password_hash="h",
            role=UserRole.ADMIN,
        )
    )
    await db_session.commit()

    with pytest.raises(IntegrityError):
        repo2 = UserRepository(db_session)
        await repo2.save(
            User(
                account_id=ACC1,
                name="B",
                email="dup@x.com",
                password_hash="h",
                role=UserRole.OPERATOR,
            )
        )
        await db_session.commit()


@pytest.mark.asyncio
async def test_count_admins(db_session: AsyncSession) -> None:
    repo = UserRepository(db_session)
    await repo.save(
        User(account_id=ACC2, name="A", email="a@x.com", password_hash="h", role=UserRole.ADMIN)
    )
    await repo.save(
        User(account_id=ACC2, name="B", email="b@x.com", password_hash="h", role=UserRole.OPERATOR)
    )
    await repo.save(
        User(account_id=ACC2, name="C", email="c@x.com", password_hash="h", role=UserRole.ADMIN)
    )
    await db_session.commit()

    count = await repo.count_active_admins(account_id=ACC2)
    assert count == 2
