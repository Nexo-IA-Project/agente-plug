from __future__ import annotations

import os
from uuid import UUID

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.adapters.db.models import SmtpConfigModel
from shared.adapters.db.repositories.smtp_config_repo import SmtpConfigRepository
from shared.config.settings import get_settings

FERNET_KEY = Fernet.generate_key().decode()

# account_id agora é UUID com FK -> accounts.
ACC1 = UUID("11111111-1111-1111-1111-111111111111")
ACC2 = UUID("22222222-2222-2222-2222-222222222222")
ACC_ABSENT = UUID("99999999-9999-9999-9999-999999999999")


@pytest.fixture(scope="session", autouse=True)
def _apply_migrations(database_url: str) -> None:
    """Aplica alembic migrations no testcontainer Postgres uma vez por sessão."""
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
async def _clean_smtp(db_session: AsyncSession) -> None:
    await db_session.execute(delete(SmtpConfigModel))
    for acc in (ACC1, ACC2):
        await db_session.execute(
            text(
                "INSERT INTO accounts (id, name, settings, created_at) "
                "VALUES (:id, :name, '{}'::jsonb, NOW()) ON CONFLICT (id) DO NOTHING"
            ),
            {"id": str(acc), "name": f"acc-{acc}"},
        )
    await db_session.commit()


@pytest.fixture(autouse=True)
def _patch_fernet_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INTEGRATION_CREDENTIALS_KEY", FERNET_KEY)
    get_settings.cache_clear()  # type: ignore[attr-defined]
    yield
    get_settings.cache_clear()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_upsert_and_get(db_session: AsyncSession) -> None:
    repo = SmtpConfigRepository(db_session)
    await repo.upsert(
        account_id=ACC1,
        host="smtp.gmail.com",
        port=587,
        username="user@gmail.com",
        password_plaintext="mysecret",
        use_tls=True,
        from_name="NexoIA",
        from_email="from@gmail.com",
    )
    await db_session.flush()

    cfg = await repo.get(account_id=ACC1)
    assert cfg is not None
    assert cfg.host == "smtp.gmail.com"
    assert cfg.port == 587
    plain = repo.decrypt_password(cfg.encrypted_password)
    assert plain == "mysecret"


@pytest.mark.asyncio
async def test_upsert_updates_existing(db_session: AsyncSession) -> None:
    repo = SmtpConfigRepository(db_session)
    await repo.upsert(
        account_id=ACC2,
        host="smtp1.com",
        port=25,
        username="u",
        password_plaintext="p1",
        use_tls=False,
        from_name="A",
        from_email="a@a.com",
    )
    await db_session.flush()

    await repo.upsert(
        account_id=ACC2,
        host="smtp2.com",
        port=587,
        username="u2",
        password_plaintext="p2",
        use_tls=True,
        from_name="B",
        from_email="b@b.com",
    )
    await db_session.flush()

    cfg = await repo.get(account_id=ACC2)
    assert cfg is not None
    assert cfg.host == "smtp2.com"
    assert cfg.port == 587
    assert repo.decrypt_password(cfg.encrypted_password) == "p2"


@pytest.mark.asyncio
async def test_get_returns_none_when_absent(db_session: AsyncSession) -> None:
    repo = SmtpConfigRepository(db_session)
    assert await repo.get(account_id=ACC_ABSENT) is None
