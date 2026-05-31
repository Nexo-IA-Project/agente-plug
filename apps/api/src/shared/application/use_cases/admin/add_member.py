from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from shared.adapters.db.repositories.identity_repo import IdentityRepository
from shared.adapters.db.repositories.membership_repo import MembershipRepository
from shared.adapters.email.smtp_email_service import SmtpEmailService
from shared.adapters.email.templates import welcome_email
from shared.adapters.kb.jwt_handler import hash_password
from shared.domain.entities.identity import Identity
from shared.domain.entities.membership import Membership
from shared.domain.entities.user import UserRole
from shared.utils.password_generator import generate_temp_password


@dataclass
class AddMemberResult:
    membership: Membership
    identity: Identity
    created_identity: bool


@dataclass
class AddMemberUseCase:
    identity_repo: IdentityRepository
    membership_repo: MembershipRepository
    email_service: SmtpEmailService

    async def execute(
        self,
        account_id: UUID,
        name: str,
        email: str,
        role: UserRole,
        profile_id: UUID | None,
    ) -> AddMemberResult:
        identity = await self.identity_repo.get_by_email(email)
        created = False

        if identity is None:
            temp_password = generate_temp_password()
            identity = Identity(
                email=email,
                password_hash=hash_password(temp_password),
                name=name,
                must_change_password=True,
                is_active=True,
            )
            await self.identity_repo.save(identity)
            created = True
        else:
            temp_password = None  # não usada no caminho silencioso

        existing_membership = await self.membership_repo.get_by_identity_and_account(
            identity.id, account_id
        )
        if existing_membership is not None:
            raise ValueError("Esta pessoa já faz parte desta empresa")

        membership = Membership(
            identity_id=identity.id,
            account_id=account_id,
            role=role,
            profile_id=profile_id,
            is_owner=False,
            is_active=True,
        )
        await self.membership_repo.save(membership)

        if created and temp_password is not None:
            subject, body = welcome_email(name=name, email=email, temp_password=temp_password)
            await self.email_service.send_email(to=email, subject=subject, body_html=body)

        return AddMemberResult(
            membership=membership,
            identity=identity,
            created_identity=created,
        )
