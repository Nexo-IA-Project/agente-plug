# apps/api/src/shared/application/use_cases/admin/get_account_config.py
from __future__ import annotations

from shared.adapters.db.repositories.account_config_repo import AccountConfigRepository
from shared.domain.entities.account_config import AccountConfig


class GetAccountConfig:
    def __init__(self, repo: AccountConfigRepository) -> None:
        self._repo = repo

    async def execute(self, account_id: int) -> AccountConfig:
        return await self._repo.get(account_id=account_id)
