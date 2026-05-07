# apps/api/src/shared/application/use_cases/admin/update_account_config.py
from __future__ import annotations

from shared.adapters.db.repositories.account_config_repo import AccountConfigRepository
from shared.domain.entities.account_config import AccountConfig, AccountConfigPatch


class UpdateAccountConfig:
    def __init__(self, repo: AccountConfigRepository) -> None:
        self._repo = repo

    async def execute(self, account_id: int, patch: AccountConfigPatch) -> AccountConfig:
        self._validate(patch)
        return await self._repo.update(account_id=account_id, patch=patch)

    def _validate(self, patch: AccountConfigPatch) -> None:
        if patch.intent_confidence_threshold is not None:
            if not 0.0 <= patch.intent_confidence_threshold <= 1.0:
                raise ValueError(
                    "intent_confidence_threshold deve estar entre 0.0 e 1.0"
                )
        if patch.cademi_max_retries is not None and patch.cademi_max_retries < 0:
            raise ValueError("cademi_max_retries não pode ser negativo")
