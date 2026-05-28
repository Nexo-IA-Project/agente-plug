from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.adapters.db.models import UserModel
from shared.domain.entities.user import User, UserRole


def _to_entity(m: UserModel) -> User:
    return User(
        id=m.id,
        account_id=m.account_id,
        name=m.name,
        email=m.email,
        password_hash=m.password_hash,
        role=UserRole(m.role),
        avatar=m.avatar,
        must_change_password=m.must_change_password,
        is_active=m.is_active,
        created_at=m.created_at,
        last_login_at=m.last_login_at,
    )


class UserRepository:
    """Session lifecycle managed by caller. Uses flush(), not commit()."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, user: User) -> None:
        model = UserModel(
            id=user.id,
            account_id=user.account_id,
            name=user.name,
            email=user.email,
            password_hash=user.password_hash,
            role=user.role.value,
            avatar=user.avatar,
            must_change_password=user.must_change_password,
            is_active=user.is_active,
        )
        self._session.add(model)
        await self._session.flush()

    async def get_by_id(self, user_id: str) -> User | None:
        result = await self._session.execute(
            select(UserModel).where(UserModel.id == user_id)
        )
        row = result.scalar_one_or_none()
        return _to_entity(row) if row else None

    async def get_by_email(self, account_id: int, email: str) -> User | None:
        result = await self._session.execute(
            select(UserModel)
            .where(UserModel.account_id == account_id)
            .where(UserModel.email == email)
        )
        row = result.scalar_one_or_none()
        return _to_entity(row) if row else None

    async def list_by_account(
        self, account_id: int, page: int, page_size: int
    ) -> tuple[list[User], int]:
        total_result = await self._session.execute(
            select(func.count())
            .select_from(UserModel)
            .where(UserModel.account_id == account_id)
        )
        total = total_result.scalar_one()

        result = await self._session.execute(
            select(UserModel)
            .where(UserModel.account_id == account_id)
            .order_by(UserModel.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        users = [_to_entity(m) for m in result.scalars().all()]
        return users, total

    async def update_password(
        self, user_id: str, new_hash: str, must_change_password: bool
    ) -> None:
        result = await self._session.execute(
            select(UserModel).where(UserModel.id == user_id)
        )
        m = result.scalar_one()
        m.password_hash = new_hash
        m.must_change_password = must_change_password
        await self._session.flush()

    async def update_profile(self, user_id: str, name: str) -> None:
        result = await self._session.execute(
            select(UserModel).where(UserModel.id == user_id)
        )
        m = result.scalar_one()
        m.name = name
        await self._session.flush()

    async def update_avatar(self, user_id: str, avatar: bytes) -> None:
        result = await self._session.execute(
            select(UserModel).where(UserModel.id == user_id)
        )
        m = result.scalar_one()
        m.avatar = avatar
        await self._session.flush()

    async def update_admin_fields(
        self, user_id: str, name: str, role: UserRole, is_active: bool
    ) -> None:
        result = await self._session.execute(
            select(UserModel).where(UserModel.id == user_id)
        )
        m = result.scalar_one()
        m.name = name
        m.role = role.value
        m.is_active = is_active
        await self._session.flush()

    async def touch_last_login(self, user_id: str) -> None:
        result = await self._session.execute(
            select(UserModel).where(UserModel.id == user_id)
        )
        m = result.scalar_one()
        m.last_login_at = datetime.now(UTC)
        await self._session.flush()

    async def delete(self, user_id: str) -> None:
        result = await self._session.execute(
            select(UserModel).where(UserModel.id == user_id)
        )
        m = result.scalar_one()
        await self._session.delete(m)
        await self._session.flush()

    async def count_active_admins(self, account_id: int) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(UserModel)
            .where(UserModel.account_id == account_id)
            .where(UserModel.role == UserRole.ADMIN.value)
            .where(UserModel.is_active.is_(True))
        )
        return result.scalar_one()
