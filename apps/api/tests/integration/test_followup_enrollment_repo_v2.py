"""Integration tests for FollowupEnrollmentRepository v2 methods.

Cobre:
- find_active_by_flow
- list_with_filters (paginação + filtros)
- count_steps_by_status

Pattern de fixtures inspirado em tests/integration/admin/test_followup_router.py
(testcontainers Postgres + alembic migrations + db_session real).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
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
)
from shared.adapters.db.repositories.followup_enrollment_repo import (
    FollowupEnrollmentRepository,
)
from shared.domain.entities.followup import (
    EnrollmentStatus,
    EnrollmentStepStatus,
)


# ──────────────────────────────────────────────────────────────
# Migrations no testcontainer (autouse session-scope)
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
# Fixtures: seed minimal account + course + flow + contact
# ──────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
async def _clean_db(db_session: AsyncSession) -> None:
    """Limpa todas as tabelas dependentes antes de cada teste."""
    await db_session.execute(delete(FollowupEnrollmentStepModel))
    await db_session.execute(delete(FollowupEnrollmentModel))
    await db_session.execute(delete(FollowupStepModel))
    await db_session.execute(delete(FollowupFlowModel))
    await db_session.execute(delete(CourseModel))
    await db_session.execute(delete(ContactModel))
    await db_session.execute(delete(AccountModel))
    await db_session.commit()


@pytest.fixture
async def seed_account(db_session: AsyncSession) -> AccountModel:
    account = AccountModel(id=uuid.uuid4(), name="T")
    db_session.add(account)
    await db_session.flush()
    await db_session.commit()
    return account


@pytest.fixture
async def seed_course(db_session: AsyncSession, seed_account: AccountModel) -> CourseModel:
    course = CourseModel(
        id=uuid.uuid4(),
        account_id=seed_account.id,
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
async def seed_flow(
    db_session: AsyncSession, seed_course: CourseModel
) -> FollowupFlowModel:
    flow = FollowupFlowModel(
        id=uuid.uuid4(),
        account_id=seed_course.account_id,
        course_id=seed_course.id,
        name="Flow A",
        is_active=True,
    )
    db_session.add(flow)
    await db_session.flush()
    await db_session.commit()
    return flow


@pytest.fixture
async def seed_contact(
    db_session: AsyncSession, seed_account: AccountModel
) -> ContactModel:
    contact = ContactModel(
        id=uuid.uuid4(),
        account_id=seed_account.id,
        phone="+5511999990001",
        name="Cliente",
        email="cliente@test.com",
    )
    db_session.add(contact)
    await db_session.flush()
    await db_session.commit()
    return contact


def _make_enrollment(
    *,
    account_id: uuid.UUID,
    flow_id: uuid.UUID,
    contact_id: uuid.UUID,
    contact_phone: str,
    status: EnrollmentStatus = EnrollmentStatus.ACTIVE,
) -> FollowupEnrollmentModel:
    return FollowupEnrollmentModel(
        id=uuid.uuid4(),
        account_id=account_id,
        flow_id=flow_id,
        contact_id=contact_id,
        conversation_id=f"conv-{uuid.uuid4().hex[:8]}",
        contact_phone=contact_phone,
        purchase_id=f"purchase-{uuid.uuid4().hex[:8]}",
        customer_name="Cliente",
        product_name="Curso X",
        status=status.value,
    )


# ──────────────────────────────────────────────────────────────
# Testes
# ──────────────────────────────────────────────────────────────


@pytest.mark.integration
async def test_find_active_by_flow_returns_only_active(
    db_session: AsyncSession,
    seed_account: AccountModel,
    seed_flow: FollowupFlowModel,
    seed_contact: ContactModel,
) -> None:
    # 2 ACTIVE
    for _ in range(2):
        db_session.add(
            _make_enrollment(
                account_id=seed_account.id,
                flow_id=seed_flow.id,
                contact_id=seed_contact.id,
                contact_phone=seed_contact.phone,
                status=EnrollmentStatus.ACTIVE,
            )
        )
    # 1 COMPLETED
    db_session.add(
        _make_enrollment(
            account_id=seed_account.id,
            flow_id=seed_flow.id,
            contact_id=seed_contact.id,
            contact_phone=seed_contact.phone,
            status=EnrollmentStatus.COMPLETED,
        )
    )
    await db_session.flush()
    await db_session.commit()

    repo = FollowupEnrollmentRepository(session=db_session)
    result = await repo.find_active_by_flow(seed_flow.id)

    assert len(result) == 2
    assert all(e.status == EnrollmentStatus.ACTIVE for e in result)
    assert all(e.flow_id == seed_flow.id for e in result)


@pytest.mark.integration
async def test_list_with_filters_paginates_active_enrollments(
    db_session: AsyncSession,
    seed_account: AccountModel,
    seed_flow: FollowupFlowModel,
    seed_contact: ContactModel,
) -> None:
    # 25 ACTIVE enrollments no mesmo flow
    for _ in range(25):
        db_session.add(
            _make_enrollment(
                account_id=seed_account.id,
                flow_id=seed_flow.id,
                contact_id=seed_contact.id,
                contact_phone=seed_contact.phone,
                status=EnrollmentStatus.ACTIVE,
            )
        )
    await db_session.flush()
    await db_session.commit()

    repo = FollowupEnrollmentRepository(session=db_session)
    items, total = await repo.list_with_filters(
        account_id=seed_account.id,
        flow_id=seed_flow.id,
        contact_phone=None,
        status=EnrollmentStatus.ACTIVE,
        page=1,
        page_size=10,
    )

    assert total == 25
    assert len(items) == 10
    assert all(e.status == EnrollmentStatus.ACTIVE for e in items)


@pytest.mark.integration
async def test_count_steps_by_status_returns_lowercase_dict(
    db_session: AsyncSession,
    seed_account: AccountModel,
    seed_flow: FollowupFlowModel,
    seed_contact: ContactModel,
) -> None:
    enrollment = _make_enrollment(
        account_id=seed_account.id,
        flow_id=seed_flow.id,
        contact_id=seed_contact.id,
        contact_phone=seed_contact.phone,
        status=EnrollmentStatus.ACTIVE,
    )
    db_session.add(enrollment)
    await db_session.flush()

    # 3 SENT + 2 PENDING steps
    for i in range(3):
        db_session.add(
            FollowupEnrollmentStepModel(
                id=uuid.uuid4(),
                enrollment_id=enrollment.id,
                position=i,
                delay_from_purchase_hours=i,
                meta_template_name=None,
                template_variables={},
                message_text="x",
                status=EnrollmentStepStatus.SENT.value,
            )
        )
    for i in range(2):
        db_session.add(
            FollowupEnrollmentStepModel(
                id=uuid.uuid4(),
                enrollment_id=enrollment.id,
                position=10 + i,
                delay_from_purchase_hours=10 + i,
                meta_template_name=None,
                template_variables={},
                message_text="y",
                status=EnrollmentStepStatus.PENDING.value,
            )
        )
    await db_session.flush()
    await db_session.commit()

    repo = FollowupEnrollmentRepository(session=db_session)
    counts = await repo.count_steps_by_status(enrollment.id)

    assert counts == {"sent": 3, "pending": 2}
