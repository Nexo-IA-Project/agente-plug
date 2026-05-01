from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nexoia.domain.entities.admin_user import AdminUser
from nexoia.infrastructure.db.models import AdminUserModel


class AdminUserRepository:
    """Session lifecycle managed by caller (Unit of Work). Uses flush(), not commit()."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, user: AdminUser) -> None:
        model = AdminUserModel(
            id=user.id,
            account_id=user.account_id,
            email=user.email,
            password_hash=user.password_hash,
            role=user.role.value,
        )
        self._session.add(model)
        await self._session.flush()

    async def get_by_email(
        self, account_id: int, email: str
    ) -> AdminUserModel | None:
        result = await self._session.execute(
            select(AdminUserModel)
            .where(AdminUserModel.account_id == account_id)
            .where(AdminUserModel.email == email)
        )
        return result.scalar_one_or_none()
