from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID


@pytest.mark.asyncio
async def test_set_last_onboarding_agent_id_updates_model():
    from sqlalchemy.ext.asyncio import AsyncSession
    from shared.adapters.db.repositories.conversation import ConversationRepository
    from shared.adapters.db.models import ConversationModel

    mock_session = AsyncMock(spec=AsyncSession)
    conv_model = MagicMock(spec=ConversationModel)
    conv_model.last_onboarding_agent_id = None

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = conv_model
    mock_session.execute = AsyncMock(return_value=mock_result)

    repo = ConversationRepository(session=mock_session)
    agent_id = UUID("aaaaaaaa-0000-0000-0000-000000000001")

    await repo.set_last_onboarding_agent_id(
        account_id=UUID("00000000-0000-0000-0000-000000000001"),
        chatnexo_conversation_id=42,
        agent_id=agent_id,
    )

    assert conv_model.last_onboarding_agent_id == agent_id
