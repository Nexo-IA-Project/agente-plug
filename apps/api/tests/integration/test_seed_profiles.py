"""Integration test: migração de seed de perfis Admin/Operador.

Após o ``alembic upgrade heads`` (rodado pelo fixture autouse), garantimos uma
conta e re-aplicamos o ``upgrade()`` do seed (idempotente) — necessário porque
o testcontainer sobe o schema SEM dados, e o seed só atua quando existe conta.

A primeira conta (single-tenant, primeira por ``created_at``) deve então ter os
perfis de sistema semeados:

- "Admin": is_system True, com TODAS as chaves do catálogo de permissões.
- "Operador": is_system False, sem nenhuma chave de ADMIN_ONLY_KEYS.

Pattern de fixtures: testcontainers Postgres + alembic migrations (igual a
test_scheduler_runner_commit.py).
"""

from __future__ import annotations

import os
import uuid

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from shared.adapters.db.repositories.profile_repo import ProfileRepository
from shared.domain.permissions.catalog import ADMIN_ONLY_KEYS, all_permission_keys


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


async def _ensure_account(engine: AsyncEngine) -> uuid.UUID:
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        existing = (
            await s.execute(text("SELECT id FROM accounts ORDER BY created_at LIMIT 1"))
        ).scalar()
        if existing is not None:
            return existing  # type: ignore[return-value]
        acc_id = uuid.uuid4()
        await s.execute(
            text("INSERT INTO accounts (id, name) VALUES (:i, :n)"),
            {"i": acc_id, "n": "Conta Teste Seed"},
        )
        await s.commit()
        return acc_id


def _seed_sync(sync_conn) -> None:
    """Corpo síncrono: configura o contexto alembic e roda o upgrade do seed."""
    from migrations.versions.a7b8c9d0e1f2_seed_default_profiles import upgrade

    ctx = MigrationContext.configure(sync_conn)
    with Operations.context(ctx):
        upgrade()


async def _run_seed_upgrade(engine: AsyncEngine) -> None:
    """Re-roda o upgrade() do seed sobre o engine async (idempotente).

    ``op.get_bind()`` espera uma conexão síncrona; usamos ``run_sync`` para
    expor a conexão asyncpg como sync ao corpo da migração.
    """
    async with engine.begin() as conn:
        await conn.run_sync(_seed_sync)


async def test_seed_creates_admin_and_operator_profiles(engine: AsyncEngine) -> None:
    account_id = await _ensure_account(engine)
    await _run_seed_upgrade(engine)

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        repo = ProfileRepository(s)
        admin = await repo.get_by_name(account_id, "Admin")
        operator = await repo.get_by_name(account_id, "Operador")

    all_keys = all_permission_keys()

    assert admin is not None, "perfil Admin não foi semeado"
    assert admin.is_system is True
    assert len(admin.permissions) == len(all_keys)
    assert set(admin.permissions) == set(all_keys)

    assert operator is not None, "perfil Operador não foi semeado"
    assert operator.is_system is False
    assert set(operator.permissions).isdisjoint(ADMIN_ONLY_KEYS)
    expected_operator = {k for k in all_keys if k not in ADMIN_ONLY_KEYS}
    assert set(operator.permissions) == expected_operator


async def test_seed_assigns_existing_users_by_role(engine: AsyncEngine) -> None:
    account_id = await _ensure_account(engine)

    # Cria um usuário admin e um operator ANTES do seed para validar a atribuição.
    maker = async_sessionmaker(engine, expire_on_commit=False)
    admin_user_id = str(uuid.uuid4())
    op_user_id = str(uuid.uuid4())
    async with maker() as s:
        cols = (
            (
                await s.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_name='users'"
                    )
                )
            )
            .scalars()
            .all()
        )
    has_name = "name" in cols

    base_cols = "id, account_id, email, password_hash, role, profile_id"
    base_vals = ":i, :a, :e, :ph, :r, NULL"
    if has_name:
        base_cols += ", name"
        base_vals += ", :n"

    async with maker() as s:
        for uid, email, role, name in (
            (admin_user_id, f"admin-{uid_suffix()}@seedtest.local", "admin", "Admin Seed"),
            (op_user_id, f"op-{uid_suffix()}@seedtest.local", "operator", "Op Seed"),
        ):
            params = {
                "i": uid,
                "a": account_id,
                "e": email,
                "ph": "x",
                "r": role,
            }
            if has_name:
                params["n"] = name
            await s.execute(text(f"INSERT INTO users ({base_cols}) VALUES ({base_vals})"), params)
        await s.commit()

    await _run_seed_upgrade(engine)

    async with maker() as s:
        repo = ProfileRepository(s)
        admin = await repo.get_by_name(account_id, "Admin")
        operator = await repo.get_by_name(account_id, "Operador")
        admin_pid = (
            await s.execute(text("SELECT profile_id FROM users WHERE id=:i"), {"i": admin_user_id})
        ).scalar()
        op_pid = (
            await s.execute(text("SELECT profile_id FROM users WHERE id=:i"), {"i": op_user_id})
        ).scalar()

    assert admin is not None and operator is not None
    assert admin_pid == admin.id
    assert op_pid == operator.id


_counter = 0


def uid_suffix() -> str:
    global _counter
    _counter += 1
    return f"{_counter}-{uuid.uuid4().hex[:8]}"
