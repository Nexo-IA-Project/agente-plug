"""Integration test: GET /admin/followup/flows agora retorna ``stats``.

Verifica que cada flow no response inclui ``stats.enrollments_active`` e
``stats.enrollments_completed``, calculados a partir dos enrollments.
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from shared.adapters.db.models import (
    AccountModel,
    ContactModel,
    CourseModel,
    FollowupEnrollmentModel,
    FollowupEnrollmentStepModel,
    FollowupFlowModel,
    FollowupStepModel,
    ScheduledJobModel,
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
    await db_session.execute(delete(ScheduledJobModel))
    await db_session.execute(delete(FollowupEnrollmentStepModel))
    await db_session.execute(delete(FollowupEnrollmentModel))
    await db_session.execute(delete(FollowupStepModel))
    await db_session.execute(delete(FollowupFlowModel))
    await db_session.execute(delete(CourseModel))
    await db_session.execute(delete(ContactModel))
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
async def seeded_flow_with_enrollments(
    db_session: AsyncSession, seeded_account: AccountModel
) -> FollowupFlowModel:
    course = CourseModel(
        id=uuid.uuid4(),
        account_id=seeded_account.id,
        name="Curso Stats",
        hubla_id=f"hubla-{uuid.uuid4().hex[:8]}",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(course)

    flow = FollowupFlowModel(
        id=uuid.uuid4(),
        account_id=seeded_account.id,
        course_id=course.id,
        name="Flow Stats",
        is_active=True,
    )
    db_session.add(flow)

    contact = ContactModel(
        id=uuid.uuid4(),
        account_id=seeded_account.id,
        phone="+5511999990001",
        name="Cliente Stats",
        email=None,
    )
    db_session.add(contact)
    await db_session.flush()

    # 3 active + 2 completed + 1 cancelled
    for i, st in enumerate(["active", "active", "active", "completed", "completed", "cancelled"]):
        db_session.add(
            FollowupEnrollmentModel(
                id=uuid.uuid4(),
                account_id=seeded_account.id,
                flow_id=flow.id,
                contact_id=contact.id,
                conversation_id=f"conv-{i}",
                contact_phone=contact.phone,
                purchase_id=f"purchase-{i}",
                customer_name="Cliente Stats",
                product_name="Curso Stats",
                status=st,
            )
        )

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

    class _SessionWrapper:
        def __init__(self, session: AsyncSession) -> None:
            self._session = session

        async def __aenter__(self) -> AsyncSession:
            return self._session

        async def __aexit__(self, *exc: object) -> None:
            return None

        def __getattr__(self, name: str) -> Any:
            return getattr(self._session, name)

    class _FakeSessionmaker:
        def __call__(self):
            return _SessionWrapper(db_session)

    fake_sessionmaker = _FakeSessionmaker()

    _ = fake_sessionmaker  # mantido para preservar shape do fixture
    with (
        patch(
            "interface.http.deps.admin_auth.get_settings",
            return_value=mock_settings,
        ),
        patch(
            "interface.http.routers.admin.followup.session_scope",
            new=patched_session_scope,
        ),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac


@pytest.mark.integration
async def test_flows_endpoint_returns_stats(
    client: AsyncClient,
    admin_headers: dict[str, str],
    seeded_flow_with_enrollments: FollowupFlowModel,
) -> None:
    r = await client.get("/admin/followup/flows", headers=admin_headers)
    assert r.status_code == 200, r.text
    items = r.json()
    assert items
    flow_item = next(it for it in items if it["id"] == str(seeded_flow_with_enrollments.id))
    assert "stats" in flow_item
    stats = flow_item["stats"]
    assert stats["enrollments_active"] == 3
    assert stats["enrollments_completed"] == 2
