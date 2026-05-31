from __future__ import annotations

from dataclasses import dataclass

from shared.adapters.db.repositories.identity_repo import IdentityRepository
from shared.adapters.kb.jwt_handler import hash_password, verify_password


class InvalidCurrentPasswordError(Exception):
    pass


@dataclass
class ChangeMyPasswordUseCase:
    identity_repo: IdentityRepository

    async def execute(self, identity_id: str, current_password: str, new_password: str) -> None:
        if len(new_password) < 8:
            raise ValueError("New password must be at least 8 characters")

        identity = await self.identity_repo.get_by_id(identity_id)
        if identity is None:
            raise LookupError(f"Identity {identity_id} not found")

        if not verify_password(current_password, identity.password_hash):
            raise InvalidCurrentPasswordError("Current password incorrect")

        new_hash = hash_password(new_password)
        await self.identity_repo.update_password(
            identity_id=identity_id, new_hash=new_hash, must_change_password=False
        )
