import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from nexoia.domain.entities.scheduled_job import JobType
from nexoia.domain.entities.webhook_event import WebhookSource
from nexoia.domain.value_objects.phone import Phone
from nexoia.infrastructure.db.models import AccountModel, ContactModel
from nexoia.infrastructure.db.repositories.contact import ContactRepository
from nexoia.infrastructure.db.repositories.scheduled_job import ScheduledJobRepository
from nexoia.infrastructure.db.repositories.webhook_event import WebhookEventRepository


@pytest.mark.integration
async def test_contact_upsert_creates_and_updates(db_session: AsyncSession) -> None:
    account_id = uuid.uuid4()
    db_session.add(AccountModel(id=account_id, name="T"))
    await db_session.flush()

    repo = ContactRepository(db_session)
    phone = Phone.parse("11999887766")

    c1 = await repo.upsert(account_id=account_id, phone=phone, name="Ana")
    c2 = await repo.upsert(account_id=account_id, phone=phone, name="Ana Maria")

    assert c1.id == c2.id
    assert c2.name == "Ana Maria"


@pytest.mark.integration
async def test_webhook_event_dedup(db_session: AsyncSession) -> None:
    repo = WebhookEventRepository(db_session)
    first = await repo.insert_if_new(
        source=WebhookSource.HUBLA, external_id="p-1", payload={"x": 1}
    )
    assert first is not None
    second = await repo.insert_if_new(
        source=WebhookSource.HUBLA, external_id="p-1", payload={"x": 2}
    )
    assert second is None


@pytest.mark.integration
async def test_scheduled_job_pick_due(db_session: AsyncSession) -> None:
    account_id = uuid.uuid4()
    db_session.add(AccountModel(id=account_id, name="T"))
    await db_session.flush()

    repo = ScheduledJobRepository(db_session)
    now = datetime.now(UTC)
    await repo.schedule(
        account_id=account_id,
        conversation_id=None,
        job_type=JobType.IDLE_PING,
        payload={},
        run_at=now - timedelta(seconds=1),
    )
    await repo.schedule(
        account_id=account_id,
        conversation_id=None,
        job_type=JobType.IDLE_PING,
        payload={},
        run_at=now + timedelta(minutes=5),
    )
    due = await repo.pick_due_jobs(now=now)
    assert len(due) == 1
