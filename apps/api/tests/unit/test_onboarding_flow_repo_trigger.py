from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from shared.adapters.db.repositories.onboarding_flow_repo import OnboardingFlowRepository


@pytest.mark.asyncio
async def test_list_active_by_product_and_event_returns_matching_flows():
    session = AsyncMock()
    product_id = uuid4()

    mock_flow = MagicMock()
    mock_flow.id = uuid4()
    mock_flow.account_id = uuid4()
    mock_flow.product_id = product_id
    mock_flow.name = "Boas-vindas"
    mock_flow.trigger_event_type = "subscription.activated"
    mock_flow.is_active = True
    mock_flow.created_at = None
    mock_flow.updated_at = None

    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = [mock_flow]
    session.execute = AsyncMock(return_value=result_mock)

    repo = OnboardingFlowRepository(session=session)
    flows = await repo.list_active_by_product_and_event(
        product_id=product_id, event_type="subscription.activated"
    )

    assert len(flows) == 1
    assert flows[0].trigger_event_type == "subscription.activated"


@pytest.mark.asyncio
async def test_list_active_by_product_and_events_matches_any_in_group():
    session = AsyncMock()
    product_id = uuid4()

    mock_flow = MagicMock()
    mock_flow.id = uuid4()
    mock_flow.account_id = uuid4()
    mock_flow.product_id = product_id
    mock_flow.name = "Boas-vindas"
    mock_flow.trigger_event_type = "subscription.activated"
    mock_flow.is_active = True
    mock_flow.created_at = None
    mock_flow.updated_at = None

    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = [mock_flow]
    session.execute = AsyncMock(return_value=result_mock)

    repo = OnboardingFlowRepository(session=session)
    flows = await repo.list_active_by_product_and_events(
        product_id=product_id,
        event_types=["subscription.activated", "customer.member_added"],
    )

    assert len(flows) == 1
    assert flows[0].trigger_event_type == "subscription.activated"
    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_active_by_product_and_events_empty_list_returns_empty():
    session = AsyncMock()
    repo = OnboardingFlowRepository(session=session)
    flows = await repo.list_active_by_product_and_events(product_id=uuid4(), event_types=[])
    assert flows == []
    session.execute.assert_not_called()
