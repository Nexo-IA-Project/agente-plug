from __future__ import annotations

from dataclasses import dataclass

from shared.adapters.db.repositories.user_repo import UserRepository
from shared.adapters.kb.jwt_handler import hash_password, verify_password


class InvalidCurrentPasswordError(Exception):
    pass


@dataclass
class ChangeMyPasswordUseCase:
    user_repo: UserRepository

    async def execute(
        self, user_id: str, current_password: str, new_password: str
    ) -> None:
        if len(new_password) < 8:
            raise ValueError("New password must be at least 8 characters")

        user = await self.user_repo.get_by_id(user_id)
        if user is None:
            raise LookupError(f"User {user_id} not found")

        if not verify_password(current_password, user.password_hash):
            raise InvalidCurrentPasswordError("Current password incorrect")

        new_hash = hash_password(new_password)
        await self.user_repo.update_password(
            user_id=user_id, new_hash=new_hash, must_change_password=False
        )
