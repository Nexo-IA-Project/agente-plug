from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from shared.config.settings import get_settings


@pytest.fixture(autouse=True)
def mock_settings():
    """Patch get_settings for unit tests — avoids requiring real .env."""
    settings = MagicMock()
    settings.refund_deadline_days = 7
    with patch(
        "shared.application.use_cases.refund.verificar_elegibilidade.get_settings",
        return_value=settings,
    ):
        yield settings
