from __future__ import annotations

from dataclasses import dataclass

from shared.adapters.db.repositories.user_repo import UserRepository
from shared.adapters.email.smtp_email_service import SmtpEmailService
from shared.adapters.email.templates import password_reset_email
from shared.adapters.kb.jwt_handler import hash_password
from shared.utils.password_generator import generate_temp_password


@dataclass
class ResetUserPasswordUseCase:
    user_repo: UserRepository
    email_service: SmtpEmailService

    async def execute(self, account_id: int, user_id: str) -> None:
        user = await self.user_repo.get_by_id(user_id)
        if user is None:
            raise LookupError(f"User {user_id} not found")

        temp_password = generate_temp_password()
        new_hash = hash_password(temp_password)
        await self.user_repo.update_password(
            user_id=user_id, new_hash=new_hash, must_change_password=True
        )

        subject, body = password_reset_email(name=user.name, temp_password=temp_password)
        await self.email_service.send_email(
            account_id=account_id, to=user.email, subject=subject, body_html=body
        )
