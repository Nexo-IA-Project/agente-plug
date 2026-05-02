import pytest

from shared.adapters.db.repositories.base import require_account_id
from shared.domain.errors import TenantIsolationError


def test_require_account_id_accepts_non_empty_value() -> None:
    require_account_id("123e4567-e89b-12d3-a456-426614174000")


def test_require_account_id_rejects_none() -> None:
    with pytest.raises(TenantIsolationError):
        require_account_id(None)


def test_require_account_id_rejects_empty_string() -> None:
    with pytest.raises(TenantIsolationError):
        require_account_id("")
