import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.adapters.db.models import (
    AccountModel,
    ContactModel,
    ConversationModel,
)


@pytest.mark.integration
async def test_insert_account_contact_conversation(db_session: AsyncSession) -> None:
    account_id = uuid.uuid4()
    db_session.add(AccountModel(id=account_id, name="Tenant A"))
    await db_session.flush()

    contact_id = uuid.uuid4()
    db_session.add(ContactModel(id=contact_id, account_id=account_id, phone="+5511999", name="Ana"))
    await db_session.flush()

    now = datetime.now(UTC)
    conv = ConversationModel(
        id=uuid.uuid4(),
        account_id=account_id,
        contact_id=contact_id,
        chatnexo_conversation_id=1,
        status="active",
        last_activity_at=now,
        window_expires_at=now + timedelta(hours=24),
    )
    db_session.add(conv)
    await db_session.flush()

    result = await db_session.execute(select(AccountModel).where(AccountModel.id == account_id))
    assert result.scalar_one().name == "Tenant A"
