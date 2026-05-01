from __future__ import annotations

import pytest
from redis.asyncio import Redis as ARedis
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer

from shared.adapters.db.session import create_engine


@pytest.fixture(scope="session")
def postgres_container():
    with PostgresContainer("pgvector/pgvector:pg16") as container:
        yield container


@pytest.fixture(scope="session")
def database_url(postgres_container: PostgresContainer) -> str:
    url = postgres_container.get_connection_url()
    return url.replace("psycopg2", "asyncpg")


@pytest.fixture
async def engine(database_url: str) -> AsyncEngine:
    return create_engine(database_url)


@pytest.fixture
async def db_session(engine: AsyncEngine) -> AsyncSession:
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        yield session


@pytest.fixture(scope="session")
def redis_container_session():
    with RedisContainer("redis:7-alpine") as c:
        yield c


@pytest.fixture
async def redis_client(redis_container_session) -> ARedis:
    host = redis_container_session.get_container_host_ip()
    port = redis_container_session.get_exposed_port(6379)
    client = ARedis.from_url(f"redis://{host}:{port}/0", decode_responses=True)
    yield client
    await client.flushdb()
    await client.aclose()
