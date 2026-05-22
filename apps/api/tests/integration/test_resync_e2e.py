"""Integration test: triggers de resync no router admin /followup.

Verifica que mutações em steps (create/update/delete/reorder) enfileiram
um job kind=resync_flow no job_queue.
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.adapters.db.models import (
    AccountModel,
    CourseModel,
    FollowupFlowModel,
    FollowupStepModel,
    JobQueueModel,
)
from shared.adapters.kb.jwt_handler import create_access_token

_JWT_SECRET = "test-secret-jwt-do-not-use-in-prod"


@pytest.fixture(scope="session", autouse=True)
def _apply_migrations(database_url: str) -> None:
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


@pytest.fixture(scope="session")
def admin_account_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def admin_token(admin_account_id: uuid.UUID) -> str:
    return create_access_token(
        data={
            "sub": "admin@test.com",
            "account_id": str(admin_account_id),
            "role": "admin",
        },
        secret=_JWT_SECRET,
        expire_minutes=60,
    )


@pytest.fixture
def admin_headers(admin_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def mock_settings() -> Any:
    settings = MagicMock()
    settings.jwt_secret = _JWT_SECRET
    settings.jwt_expire_minutes = 60
    settings.cors_origins = ["http://localhost:3000"]
    settings.cors_origin_regex = None
    settings.database_url = "postgresql+asyncpg://fake"
    return settings


@pytest.fixture(autouse=True)
async def _purge_other_accounts(db_session: AsyncSession, admin_account_id: uuid.UUID) -> None:
    from shared.adapters.db.models import (
        ContactModel,
        FollowupEnrollmentModel,
        FollowupEnrollmentStepModel,
    )

    await db_session.execute(delete(FollowupEnrollmentStepModel))
    await db_session.execute(delete(FollowupEnrollmentModel))
    await db_session.execute(delete(FollowupStepModel))
    await db_session.execute(delete(FollowupFlowModel))
    await db_session.execute(delete(CourseModel))
    await db_session.execute(delete(ContactModel))
    await db_session.execute(delete(JobQueueModel))
    await db_session.execute(delete(AccountModel).where(AccountModel.id != admin_account_id))
    await db_session.commit()


@pytest.fixture
async def seeded_account(db_session: AsyncSession, admin_account_id: uuid.UUID) -> AccountModel:
    existing = await db_session.get(AccountModel, admin_account_id)
    if existing is not None:
        return existing
    account = AccountModel(id=admin_account_id, name="T")
    db_session.add(account)
    await db_session.flush()
    await db_session.commit()
    return account


@pytest.fixture
async def seeded_course(db_session: AsyncSession, seeded_account: AccountModel) -> CourseModel:
    from datetime import UTC, datetime

    course = CourseModel(
        id=uuid.uuid4(),
        account_id=seeded_account.id,
        name="Curso Padrão",
        hubla_id=f"curso-{uuid.uuid4().hex[:8]}",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(course)
    await db_session.flush()
    await db_session.commit()
    return course


@pytest.fixture
async def seeded_flow(
    db_session: AsyncSession,
    seeded_course: CourseModel,
) -> FollowupFlowModel:
    flow = FollowupFlowModel(
        id=uuid.uuid4(),
        account_id=seeded_course.account_id,
        course_id=seeded_course.id,
        name="Flow X",
        is_active=True,
    )
    db_session.add(flow)
    await db_session.flush()
    await db_session.commit()
    return flow


@pytest.fixture
def patched_session_scope(db_session: AsyncSession):
    @asynccontextmanager
    async def _scope():
        try:
            yield db_session
            await db_session.commit()
        except Exception:
            await db_session.rollback()
            raise

    return _scope


@pytest.fixture
async def client(
    seeded_account: AccountModel,
    mock_settings: Any,
    patched_session_scope,
    db_session: AsyncSession,
):
    from main import app

    # Patch get_sessionmaker no router para usar a session do teste
    # via uma sessionmaker que retorna sempre a mesma session (sem fechar).
    @asynccontextmanager
    async def _noop_session_close():
        yield

    class _FakeSessionmaker:
        def __call__(self):
            # Retorna um wrapper que delega à db_session mas NÃO fecha no exit.
            return _SessionWrapper(db_session)

    class _SessionWrapper:
        def __init__(self, session: AsyncSession) -> None:
            self._session = session

        async def __aenter__(self) -> AsyncSession:
            return self._session

        async def __aexit__(self, *exc: object) -> None:
            return None

        def __getattr__(self, name: str) -> Any:
            return getattr(self._session, name)

    fake_sessionmaker = _FakeSessionmaker()

    with (
        patch(
            "interface.http.deps.admin_auth.get_settings",
            return_value=mock_settings,
        ),
        patch(
            "interface.http.routers.admin.followup.session_scope",
            new=patched_session_scope,
        ),
        patch(
            "interface.http.routers.admin.followup.get_sessionmaker",
            return_value=fake_sessionmaker,
        ),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac


@pytest.mark.integration
async def test_step_creation_enqueues_resync_job(
    client: AsyncClient,
    admin_headers: dict[str, str],
    seeded_flow: FollowupFlowModel,
    db_session: AsyncSession,
) -> None:
    """Após criar step, um job kind=resync_flow deve ser enfileirado."""
    response = await client.post(
        f"/admin/followup/flows/{seeded_flow.id}/steps",
        json={
            "delay_from_purchase_hours": 24,
            "meta_template_name": "t",
            "template_variables": {},
        },
        headers=admin_headers,
    )
    assert response.status_code == 201, response.text

    jobs = (
        (await db_session.execute(select(JobQueueModel).where(JobQueueModel.kind == "resync_flow")))
        .scalars()
        .all()
    )
    assert len(jobs) >= 1
    assert any(j.payload["flow_id"] == str(seeded_flow.id) for j in jobs)
