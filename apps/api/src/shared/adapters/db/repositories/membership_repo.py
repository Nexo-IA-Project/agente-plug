from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.adapters.db.models import AccountModel, IdentityModel, MembershipModel
from shared.domain.entities.membership import Membership
from shared.domain.entities.user import UserRole


@dataclass
class MemberView:
    membership_id: str
    identity_id: str
    account_id: UUID
    account_name: str
    email: str
    name: str
    role: UserRole
    profile_id: UUID | None
    is_owner: bool
    is_active: bool
    must_change_password: bool
    has_avatar: bool
    created_at: datetime
    last_login_at: datetime | None


def _to_entity(m: MembershipModel) -> Membership:
    return Membership(
        id=m.id,
        identity_id=m.identity_id,
        account_id=m.account_id,
        role=UserRole(m.role),
        profile_id=m.profile_id,
        is_owner=m.is_owner,
        is_active=m.is_active,
        created_at=m.created_at,
    )


class MembershipRepository:
    """Session lifecycle managed by caller. Uses flush(), not commit()."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, m: Membership) -> None:
        self._session.add(
            MembershipModel(
                id=m.id,
                identity_id=m.identity_id,
                account_id=m.account_id,
                role=m.role.value,
                profile_id=m.profile_id,
                is_owner=m.is_owner,
                is_active=m.is_active,
            )
        )
        await self._session.flush()

    async def get_by_id(self, membership_id: str) -> Membership | None:
        row = (
            await self._session.execute(
                select(MembershipModel).where(MembershipModel.id == membership_id)
            )
        ).scalar_one_or_none()
        return _to_entity(row) if row else None

    async def get_by_identity_and_account(
        self, identity_id: str, account_id: UUID
    ) -> Membership | None:
        row = (
            await self._session.execute(
                select(MembershipModel)
                .where(MembershipModel.identity_id == identity_id)
                .where(MembershipModel.account_id == account_id)
            )
        ).scalar_one_or_none()
        return _to_entity(row) if row else None

    async def list_active_by_identity(self, identity_id: str) -> list[MemberView]:
        rows = (
            await self._session.execute(
                select(MembershipModel, AccountModel, IdentityModel)
                .join(AccountModel, AccountModel.id == MembershipModel.account_id)
                .join(IdentityModel, IdentityModel.id == MembershipModel.identity_id)
                .where(MembershipModel.identity_id == identity_id)
                .where(MembershipModel.is_active.is_(True))
                .order_by(AccountModel.name.asc())
            )
        ).all()
        return [self._view(m, acc, ident) for m, acc, ident in rows]

    async def list_by_account(
        self, account_id: UUID, page: int, page_size: int
    ) -> tuple[list[MemberView], int]:
        total = (
            await self._session.execute(
                select(func.count())
                .select_from(MembershipModel)
                .where(MembershipModel.account_id == account_id)
            )
        ).scalar_one()
        rows = (
            await self._session.execute(
                select(MembershipModel, AccountModel, IdentityModel)
                .join(AccountModel, AccountModel.id == MembershipModel.account_id)
                .join(IdentityModel, IdentityModel.id == MembershipModel.identity_id)
                .where(MembershipModel.account_id == account_id)
                .order_by(MembershipModel.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
        return [self._view(m, acc, ident) for m, acc, ident in rows], total

    async def update_fields(
        self, membership_id: str, role: UserRole, is_active: bool, profile_id: UUID | None
    ) -> None:
        m = (
            await self._session.execute(
                select(MembershipModel).where(MembershipModel.id == membership_id)
            )
        ).scalar_one()
        m.role = role.value
        m.is_active = is_active
        m.profile_id = profile_id
        await self._session.flush()

    async def delete(self, membership_id: str) -> None:
        m = (
            await self._session.execute(
                select(MembershipModel).where(MembershipModel.id == membership_id)
            )
        ).scalar_one()
        await self._session.delete(m)
        await self._session.flush()

    async def count_active_admins(self, account_id: UUID) -> int:
        return (
            await self._session.execute(
                select(func.count())
                .select_from(MembershipModel)
                .where(MembershipModel.account_id == account_id)
                .where(MembershipModel.role == UserRole.ADMIN.value)
                .where(MembershipModel.is_active.is_(True))
            )
        ).scalar_one()

    @staticmethod
    def _view(m: MembershipModel, acc: AccountModel, ident: IdentityModel) -> MemberView:
        return MemberView(
            membership_id=m.id,
            identity_id=m.identity_id,
            account_id=m.account_id,
            account_name=acc.name,
            email=ident.email,
            name=ident.name,
            role=UserRole(m.role),
            profile_id=m.profile_id,
            is_owner=m.is_owner,
            is_active=m.is_active,
            must_change_password=ident.must_change_password,
            has_avatar=ident.avatar is not None,
            created_at=m.created_at,
            last_login_at=ident.last_login_at,
        )
