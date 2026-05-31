from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from shared.adapters.db.repositories.identity_repo import IdentityRepository
from shared.adapters.email.smtp_email_service import SmtpEmailService
from shared.adapters.email.templates import password_reset_email
from shared.adapters.kb.jwt_handler import hash_password
from shared.utils.password_generator import generate_temp_password


@dataclass
class ResetUserPasswordUseCase:
    identity_repo: IdentityRepository
    email_service: SmtpEmailService

    async def execute(self, account_id: UUID, identity_id: str) -> None:
        identity = await self.identity_repo.get_by_id(identity_id)
        if identity is None:
            raise LookupError(f"Identity {identity_id} not found")

        temp_password = generate_temp_password()
        new_hash = hash_password(temp_password)
        await self.identity_repo.update_password(
            identity_id=identity_id, new_hash=new_hash, must_change_password=True
        )

        subject, body = password_reset_email(name=identity.name, temp_password=temp_password)
        await self.email_service.send_email(to=identity.email, subject=subject, body_html=body)
