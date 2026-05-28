from __future__ import annotations

from dataclasses import dataclass

from shared.adapters.db.repositories.user_repo import UserRepository
from shared.adapters.email.smtp_email_service import SmtpEmailService
from shared.adapters.email.templates import welcome_email
from shared.adapters.kb.jwt_handler import hash_password
from shared.domain.entities.user import User, UserRole
from shared.utils.password_generator import generate_temp_password


@dataclass
class CreateUserUseCase:
    user_repo: UserRepository
    email_service: SmtpEmailService

    async def execute(self, account_id: int, name: str, email: str, role: UserRole) -> User:
        existing = await self.user_repo.get_by_email(account_id=account_id, email=email)
        if existing is not None:
            raise ValueError(f"User with email {email} already exists")

        temp_password = generate_temp_password()
        password_hash = hash_password(temp_password)

        user = User(
            account_id=account_id,
            name=name,
            email=email,
            password_hash=password_hash,
            role=role,
            must_change_password=True,
            is_active=True,
        )
        await self.user_repo.save(user)

        subject, body = welcome_email(name=name, email=email, temp_password=temp_password)
        await self.email_service.send_email(
            account_id=account_id, to=email, subject=subject, body_html=body
        )
        return user
