from __future__ import annotations

import uuid
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.adapters.db.models import MembershipModel, ProfileModel, ProfilePermissionModel
from shared.domain.entities.profile import Profile


@dataclass
class ProfileRepository:
    session: AsyncSession

    async def create(
        self, *, account_id: UUID, name: str, is_system: bool, permissions: list[str]
    ) -> Profile:
        model = ProfileModel(id=uuid.uuid4(), account_id=account_id, name=name, is_system=is_system)
        self.session.add(model)
        await self.session.flush()
        ordered = list(dict.fromkeys(permissions))  # dedup preservando ordem
        for key in ordered:
            self.session.add(
                ProfilePermissionModel(id=uuid.uuid4(), profile_id=model.id, permission_key=key)
            )
        await self.session.flush()
        return Profile(
            id=model.id, account_id=account_id, name=name, is_system=is_system, permissions=ordered
        )

    async def _perms(self, profile_id: UUID) -> list[str]:
        rows = (
            (
                await self.session.execute(
                    select(ProfilePermissionModel.permission_key).where(
                        ProfilePermissionModel.profile_id == profile_id
                    )
                )
            )
            .scalars()
            .all()
        )
        return list(rows)

    async def get_by_name(self, account_id: UUID, name: str) -> Profile | None:
        m = (
            await self.session.execute(
                select(ProfileModel).where(
                    ProfileModel.account_id == account_id, ProfileModel.name == name
                )
            )
        ).scalar_one_or_none()
        if m is None:
            return None
        return Profile(
            id=m.id,
            account_id=m.account_id,
            name=m.name,
            is_system=m.is_system,
            permissions=await self._perms(m.id),
        )

    async def get_by_id(self, account_id: UUID, profile_id: UUID) -> Profile | None:
        m = (
            await self.session.execute(
                select(ProfileModel).where(
                    ProfileModel.account_id == account_id, ProfileModel.id == profile_id
                )
            )
        ).scalar_one_or_none()
        if m is None:
            return None
        return Profile(
            id=m.id,
            account_id=m.account_id,
            name=m.name,
            is_system=m.is_system,
            permissions=await self._perms(m.id),
        )

    async def update(
        self, *, account_id: UUID, profile_id: UUID, name: str, permissions: list[str]
    ) -> Profile | None:
        m = (
            await self.session.execute(
                select(ProfileModel).where(
                    ProfileModel.account_id == account_id, ProfileModel.id == profile_id
                )
            )
        ).scalar_one_or_none()
        if m is None:
            return None
        m.name = name
        m.updated_at = func.now()
        # substitui o conjunto de permissions
        await self.session.execute(
            sa_delete(ProfilePermissionModel).where(ProfilePermissionModel.profile_id == profile_id)
        )
        ordered = list(dict.fromkeys(permissions))  # dedup preservando ordem
        for key in ordered:
            self.session.add(
                ProfilePermissionModel(id=uuid.uuid4(), profile_id=profile_id, permission_key=key)
            )
        await self.session.flush()
        return Profile(
            id=m.id,
            account_id=m.account_id,
            name=m.name,
            is_system=m.is_system,
            permissions=ordered,
        )

    async def delete(self, account_id: UUID, profile_id: UUID) -> bool:
        m = (
            await self.session.execute(
                select(ProfileModel).where(
                    ProfileModel.account_id == account_id, ProfileModel.id == profile_id
                )
            )
        ).scalar_one_or_none()
        if m is None:
            return False
        await self.session.delete(m)
        await self.session.flush()
        return True

    async def list_with_counts(self, account_id: UUID) -> list[dict[str, object]]:
        perm_count = (
            select(
                ProfilePermissionModel.profile_id.label("profile_id"),
                func.count().label("permission_count"),
            )
            .group_by(ProfilePermissionModel.profile_id)
            .subquery()
        )
        user_count = (
            select(
                MembershipModel.profile_id.label("profile_id"),
                func.count().label("user_count"),
            )
            .where(
                MembershipModel.profile_id.is_not(None),
                MembershipModel.account_id == account_id,
            )
            .group_by(MembershipModel.profile_id)
            .subquery()
        )
        stmt = (
            select(
                ProfileModel.id,
                ProfileModel.name,
                ProfileModel.is_system,
                func.coalesce(perm_count.c.permission_count, 0).label("permission_count"),
                func.coalesce(user_count.c.user_count, 0).label("user_count"),
            )
            .outerjoin(perm_count, perm_count.c.profile_id == ProfileModel.id)
            .outerjoin(user_count, user_count.c.profile_id == ProfileModel.id)
            .where(ProfileModel.account_id == account_id)
            .order_by(ProfileModel.name)
        )
        rows = (await self.session.execute(stmt)).all()
        return [
            {
                "id": r.id,
                "name": r.name,
                "is_system": r.is_system,
                "permission_count": int(r.permission_count),
                "user_count": int(r.user_count),
            }
            for r in rows
        ]

    async def name_map(self, account_id: UUID) -> dict[UUID, str]:
        """Mapa {profile_id: name} de todos os profiles da account (evita N+1)."""
        rows = (
            await self.session.execute(
                select(ProfileModel.id, ProfileModel.name).where(
                    ProfileModel.account_id == account_id
                )
            )
        ).all()
        return {r.id: r.name for r in rows}

    async def list_by_account(self, account_id: UUID) -> list[Profile]:
        rows = (
            (
                await self.session.execute(
                    select(ProfileModel)
                    .where(ProfileModel.account_id == account_id)
                    .order_by(ProfileModel.name)
                )
            )
            .scalars()
            .all()
        )
        out: list[Profile] = []
        for m in rows:
            out.append(
                Profile(
                    id=m.id,
                    account_id=m.account_id,
                    name=m.name,
                    is_system=m.is_system,
                    permissions=await self._perms(m.id),
                )
            )
        return out
