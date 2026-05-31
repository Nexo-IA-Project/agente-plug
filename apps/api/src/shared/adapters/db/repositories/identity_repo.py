from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.adapters.db.models import IdentityModel
from shared.domain.entities.identity import Identity


def _to_entity(m: IdentityModel) -> Identity:
    return Identity(
        id=m.id,
        email=m.email,
        password_hash=m.password_hash,
        name=m.name,
        avatar=m.avatar,
        must_change_password=m.must_change_password,
        is_active=m.is_active,
        created_at=m.created_at,
        last_login_at=m.last_login_at,
    )


class IdentityRepository:
    """Session lifecycle managed by caller. Uses flush(), not commit()."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, ident: Identity) -> None:
        self._session.add(
            IdentityModel(
                id=ident.id,
                email=ident.email,
                password_hash=ident.password_hash,
                name=ident.name,
                avatar=ident.avatar,
                must_change_password=ident.must_change_password,
                is_active=ident.is_active,
            )
        )
        await self._session.flush()

    async def get_by_id(self, identity_id: str) -> Identity | None:
        row = (
            await self._session.execute(
                select(IdentityModel).where(IdentityModel.id == identity_id)
            )
        ).scalar_one_or_none()
        return _to_entity(row) if row else None

    async def get_by_email(self, email: str) -> Identity | None:
        row = (
            await self._session.execute(
                select(IdentityModel).where(func.lower(IdentityModel.email) == email.lower())
            )
        ).scalar_one_or_none()
        return _to_entity(row) if row else None

    async def update_password(
        self, identity_id: str, new_hash: str, must_change_password: bool
    ) -> None:
        m = (
            await self._session.execute(
                select(IdentityModel).where(IdentityModel.id == identity_id)
            )
        ).scalar_one()
        m.password_hash = new_hash
        m.must_change_password = must_change_password
        await self._session.flush()

    async def update_profile(self, identity_id: str, name: str) -> None:
        m = (
            await self._session.execute(
                select(IdentityModel).where(IdentityModel.id == identity_id)
            )
        ).scalar_one()
        m.name = name
        await self._session.flush()

    async def update_avatar(self, identity_id: str, avatar: bytes) -> None:
        m = (
            await self._session.execute(
                select(IdentityModel).where(IdentityModel.id == identity_id)
            )
        ).scalar_one()
        m.avatar = avatar
        await self._session.flush()

    async def touch_last_login(self, identity_id: str) -> None:
        m = (
            await self._session.execute(
                select(IdentityModel).where(IdentityModel.id == identity_id)
            )
        ).scalar_one()
        m.last_login_at = datetime.now(UTC)
        await self._session.flush()
