from __future__ import annotations

import uuid
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.adapters.db.models import ProfileModel, ProfilePermissionModel
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
