from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from shared.adapters.db.session import create_engine
from shared.config.settings import get_settings


@pytest.fixture(scope="session")
def database_url() -> str:
    return get_settings().database_url


@pytest.fixture
async def engine(database_url: str) -> AsyncIterator[AsyncEngine]:
    eng = create_engine(database_url)
    yield eng
    await eng.dispose()


@pytest.fixture
async def db_session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """Sessão com rollback automático no fim do teste.

    Roda contra o postgres já levantado pelo docker compose com migrations
    aplicadas. Cada teste fica isolado via SAVEPOINT + rollback final.
    """
    async with engine.connect() as conn:
        trans = await conn.begin()
        maker = async_sessionmaker(bind=conn, expire_on_commit=False)
        async with maker() as session:
            try:
                yield session
            finally:
                await trans.rollback()
