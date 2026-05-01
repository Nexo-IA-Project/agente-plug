from __future__ import annotations

from typing import Any
from uuid import UUID

from shared.domain.errors import TenantIsolationError


def require_account_id(account_id: Any) -> None:
    """Raise if a repository method is called without an account_id scope."""
    if account_id is None:
        raise TenantIsolationError("account_id is required for this query")
    if isinstance(account_id, str) and not account_id:
        raise TenantIsolationError("account_id must be a non-empty string")
    if isinstance(account_id, UUID) and account_id.int == 0:
        raise TenantIsolationError("account_id must not be the zero UUID")
