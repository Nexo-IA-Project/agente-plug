import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from nexoia.application.memory.legal_history import LegalHistoryChecker


async def test_returns_true_when_refund_mentioned_within_7_days():
    purchase_date = datetime(2026, 1, 1, tzinfo=UTC)
    repo = AsyncMock()
    repo.find_refund_mentions = AsyncMock(return_value=["msg-1"])

    checker = LegalHistoryChecker(message_repo=repo)
    result = await checker.has_prior_refund_mention(
        account_id=uuid.uuid4(),
        contact_id=uuid.uuid4(),
        purchase_date=purchase_date,
    )
    assert result is True
    repo.find_refund_mentions.assert_awaited_once()


async def test_returns_false_when_no_mentions():
    repo = AsyncMock()
    repo.find_refund_mentions = AsyncMock(return_value=[])

    checker = LegalHistoryChecker(message_repo=repo)
    result = await checker.has_prior_refund_mention(
        account_id=uuid.uuid4(),
        contact_id=uuid.uuid4(),
        purchase_date=datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert result is False


async def test_window_is_7_days():
    purchase_date = datetime(2026, 1, 1, tzinfo=UTC)
    captured = {}
    repo = AsyncMock()

    async def capture(**kwargs):
        captured.update(kwargs)
        return []

    repo.find_refund_mentions = capture

    checker = LegalHistoryChecker(message_repo=repo)
    await checker.has_prior_refund_mention(
        account_id=uuid.uuid4(),
        contact_id=uuid.uuid4(),
        purchase_date=purchase_date,
    )
    assert captured["window_end"] == purchase_date + timedelta(days=7)
