"""Integration tests: migration v2 do follow-up engine.

Verifica que após `alembic upgrade heads`:
- Colunas novas (failure_reason, flow_step_id) existem em followup_enrollment_steps.
- scheduled_job_id continua existindo (criada anteriormente, mantida pela v2).
- Índice UNIQUE de dedup foi criado em followup_enrollments.
- Índices de leitura foram criados.
- FK fk_followup_enrollments_flow existe com ON DELETE SET NULL.
- O valor 'cancelled' está presente no enum Python EnrollmentStepStatus.

Estratégia: usa testcontainers (postgres) + roda alembic upgrade no setup.
"""

from __future__ import annotations

import pytest
from shared.domain.entities.followup import EnrollmentStepStatus
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# ──────────────────────────────────────────────────────────────
# Migrations no testcontainer (autouse)
# ──────────────────────────────────────────────────────────────


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


# ──────────────────────────────────────────────────────────────
# Testes
# ──────────────────────────────────────────────────────────────


@pytest.mark.integration
async def test_migration_added_failure_reason_column(db_session: AsyncSession) -> None:
    result = await db_session.execute(
        text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'followup_enrollment_steps' "
            "AND column_name = 'failure_reason'"
        )
    )
    assert result.scalar_one_or_none() == "failure_reason"


@pytest.mark.integration
async def test_migration_kept_scheduled_job_id_column(db_session: AsyncSession) -> None:
    """scheduled_job_id foi criada anteriormente (a2b3c4d5e6f7); deve continuar existindo."""
    result = await db_session.execute(
        text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'followup_enrollment_steps' "
            "AND column_name = 'scheduled_job_id'"
        )
    )
    assert result.scalar_one_or_none() == "scheduled_job_id"


@pytest.mark.integration
async def test_migration_added_flow_step_id_column(db_session: AsyncSession) -> None:
    result = await db_session.execute(
        text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'followup_enrollment_steps' "
            "AND column_name = 'flow_step_id'"
        )
    )
    assert result.scalar_one_or_none() == "flow_step_id"


@pytest.mark.integration
async def test_migration_added_dedup_unique_index(db_session: AsyncSession) -> None:
    result = await db_session.execute(
        text(
            "SELECT indexname FROM pg_indexes "
            "WHERE tablename = 'followup_enrollments' "
            "AND indexname = 'uq_followup_enrollment_dedup'"
        )
    )
    assert result.scalar_one_or_none() == "uq_followup_enrollment_dedup"


@pytest.mark.integration
async def test_migration_added_flow_fk_with_set_null(db_session: AsyncSession) -> None:
    """FK followup_enrollments.flow_id -> followup_flows.id com ON DELETE SET NULL."""
    result = await db_session.execute(
        text("SELECT confdeltype FROM pg_constraint WHERE conname = 'fk_followup_enrollments_flow'")
    )
    # confdeltype: 'n' = SET NULL, 'a' = NO ACTION, 'c' = CASCADE, 'r' = RESTRICT
    # asyncpg retorna como bytes para tipo "char" do Postgres
    value = result.scalar_one_or_none()
    assert value in ("n", b"n")


@pytest.mark.integration
async def test_enrollment_step_status_enum_has_cancelled() -> None:
    """O enum Python EnrollmentStepStatus deve incluir CANCELLED."""
    assert EnrollmentStepStatus.CANCELLED.value == "cancelled"
    assert "cancelled" in {s.value for s in EnrollmentStepStatus}
