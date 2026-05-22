"""Integration test: router /admin/followup/enrollments.

Cobre:
- GET /admin/followup/enrollments (paginação + filtros)
- GET /admin/followup/enrollments/{id}/steps

Pattern: testcontainers Postgres + alembic migrations + db_session real,
seguindo o estilo de test_followup_router.py.
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
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

# ──────────────────────────────────────────────────────────────
# Constantes
# ──────────────────────────────────────────────────────────────
_JWT_SECRET = "test-secret-jwt-do-not-use-in-prod"


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
# Fixtures
# ──────────────────────────────────────────────────────────────


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
    """Garante que apenas o admin_account_id existe e limpa state residual."""
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
async def seeded_course(db_session: AsyncSession, seeded_account: AccountModel) -> CourseModel:
    course = CourseModel(
        id=uuid.uuid4(),
        account_id=seeded_account.id,
        name="Curso X",
        hubla_id=f"hubla-{uuid.uuid4().hex[:8]}",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(course)
    await db_session.flush()
    await db_session.commit()
    return course


@pytest.fixture
async def seeded_flow(db_session: AsyncSession, seeded_course: CourseModel) -> FollowupFlowModel:
    flow = FollowupFlowModel(
        id=uuid.uuid4(),
        account_id=seeded_course.account_id,
        course_id=seeded_course.id,
        name="Flow Y",
        is_active=True,
    )
    db_session.add(flow)
    await db_session.flush()
    await db_session.commit()
    return flow


@pytest.fixture
async def seeded_contact(db_session: AsyncSession, seeded_account: AccountModel) -> ContactModel:
    contact = ContactModel(
        id=uuid.uuid4(),
        account_id=seeded_account.id,
        phone="+5511999990001",
        name="Cliente Teste",
        email="cliente@test.com",
    )
    db_session.add(contact)
    await db_session.flush()
    await db_session.commit()
    return contact


@pytest.fixture
async def seeded_enrollments(
    db_session: AsyncSession,
    seeded_flow: FollowupFlowModel,
    seeded_contact: ContactModel,
) -> list[FollowupEnrollmentModel]:
    """3 enrollments: 2 active + 1 completed."""
    enrollments: list[FollowupEnrollmentModel] = []
    for i, status_val in enumerate(["active", "active", "completed"]):
        e = FollowupEnrollmentModel(
            id=uuid.uuid4(),
            account_id=seeded_flow.account_id,
            flow_id=seeded_flow.id,
            contact_id=seeded_contact.id,
            conversation_id=f"conv-{i}",
            contact_phone=seeded_contact.phone,
            purchase_id=f"purchase-{i}",
            customer_name="Cliente Teste",
            product_name="Curso X",
            status=status_val,
        )
        db_session.add(e)
        enrollments.append(e)
    await db_session.flush()
    await db_session.commit()
    return enrollments


@pytest.fixture
async def seeded_enrollment_with_steps(
    db_session: AsyncSession,
    seeded_flow: FollowupFlowModel,
    seeded_contact: ContactModel,
) -> FollowupEnrollmentModel:
    enrollment = FollowupEnrollmentModel(
        id=uuid.uuid4(),
        account_id=seeded_flow.account_id,
        flow_id=seeded_flow.id,
        contact_id=seeded_contact.id,
        conversation_id="conv-steps",
        contact_phone=seeded_contact.phone,
        purchase_id="purchase-steps",
        customer_name="Cliente Teste",
        product_name="Curso X",
        status="active",
    )
    db_session.add(enrollment)
    await db_session.flush()

    # scheduled_job para o primeiro step
    sj = ScheduledJobModel(
        id=uuid.uuid4(),
        account_id=seeded_flow.account_id,
        conversation_id=None,
        job_type="followup_step",
        payload={},
        run_at=datetime.now(UTC) + timedelta(hours=24),
        status="pending",
    )
    db_session.add(sj)
    await db_session.flush()

    # 2 steps: 1 SENT + 1 PENDING (com scheduled_job)
    db_session.add(
        FollowupEnrollmentStepModel(
            id=uuid.uuid4(),
            enrollment_id=enrollment.id,
            position=0,
            delay_from_purchase_hours=0,
            meta_template_name="welcome",
            template_variables={},
            message_text=None,
            scheduled_job_id=None,
            status="sent",
            sent_at=datetime.now(UTC),
        )
    )
    db_session.add(
        FollowupEnrollmentStepModel(
            id=uuid.uuid4(),
            enrollment_id=enrollment.id,
            position=1,
            delay_from_purchase_hours=24,
            meta_template_name=None,
            template_variables={},
            message_text="Olá, tudo bem por aí?",
            scheduled_job_id=sj.id,
            status="pending",
        )
    )
    await db_session.flush()
    await db_session.commit()
    return enrollment


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

    with (
        patch(
            "interface.http.deps.admin_auth.get_settings",
            return_value=mock_settings,
        ),
        patch(
            "interface.http.routers.admin.followup_enrollments.session_scope",
            new=patched_session_scope,
        ),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac


# ──────────────────────────────────────────────────────────────
# Testes
# ──────────────────────────────────────────────────────────────


@pytest.mark.integration
async def test_list_enrollments_paginates(
    client: AsyncClient,
    admin_headers: dict[str, str],
    seeded_enrollments: list[FollowupEnrollmentModel],
) -> None:
    r = await client.get(
        "/admin/followup/enrollments?page=1&page_size=10",
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] >= 3
    assert body["page"] == 1
    assert body["page_size"] == 10
    assert len(body["items"]) <= 10
    item = body["items"][0]
    for key in [
        "id",
        "contact_phone",
        "customer_name",
        "flow_id",
        "flow_name",
        "course_name",
        "status",
        "created_at",
        "steps_sent",
        "steps_total",
    ]:
        assert key in item
    assert item["flow_name"] == "Flow Y"
    assert item["course_name"] == "Curso X"


@pytest.mark.integration
async def test_filter_by_status_active(
    client: AsyncClient,
    admin_headers: dict[str, str],
    seeded_enrollments: list[FollowupEnrollmentModel],
) -> None:
    r = await client.get(
        "/admin/followup/enrollments?status=active",
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 2
    assert all(it["status"] == "active" for it in body["items"])


@pytest.mark.integration
async def test_filter_by_status_invalid_returns_400(
    client: AsyncClient,
    admin_headers: dict[str, str],
    seeded_enrollments: list[FollowupEnrollmentModel],
) -> None:
    r = await client.get(
        "/admin/followup/enrollments?status=foobar",
        headers=admin_headers,
    )
    assert r.status_code == 400, r.text


@pytest.mark.integration
async def test_get_steps_returns_expected_fields(
    client: AsyncClient,
    admin_headers: dict[str, str],
    seeded_enrollment_with_steps: FollowupEnrollmentModel,
) -> None:
    enr_id = seeded_enrollment_with_steps.id
    r = await client.get(
        f"/admin/followup/enrollments/{enr_id}/steps",
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body, list)
    assert len(body) == 2

    sent_step = body[0]
    pending_step = body[1]

    for key in [
        "id",
        "position",
        "delay_from_purchase_hours",
        "template_name",
        "message_text_preview",
        "status",
        "sent_at",
        "scheduled_for",
        "failure_reason",
    ]:
        assert key in sent_step
        assert key in pending_step

    assert sent_step["status"] == "sent"
    assert sent_step["template_name"] == "welcome"
    assert sent_step["sent_at"] is not None

    assert pending_step["status"] == "pending"
    assert pending_step["scheduled_for"] is not None
    assert pending_step["message_text_preview"] == "Olá, tudo bem por aí?"
