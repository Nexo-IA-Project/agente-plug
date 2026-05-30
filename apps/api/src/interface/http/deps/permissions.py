from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from interface.http.deps.admin_auth import AdminAuth, require_admin
from shared.adapters.db.models import ProfilePermissionModel, UserModel
from shared.adapters.db.session import session_scope
from shared.domain.permissions.catalog import all_permission_keys


async def resolve_user_permissions(session: AsyncSession, *, user_id: str, role: str) -> set[str]:
    if role == "admin":
        return set(all_permission_keys())
    profile_id = (
        await session.execute(select(UserModel.profile_id).where(UserModel.id == user_id))
    ).scalar_one_or_none()
    if profile_id is None:
        return set()
    rows = (
        (
            await session.execute(
                select(ProfilePermissionModel.permission_key).where(
                    ProfilePermissionModel.profile_id == profile_id
                )
            )
        )
        .scalars()
        .all()
    )
    return set(rows)


def require_permission(key: str) -> Callable[..., Awaitable[AdminAuth]]:
    async def _dep(auth: AdminAuth = Depends(require_admin)) -> AdminAuth:
        if auth.user_role == "admin":
            return auth
        async with session_scope() as session:
            perms = await resolve_user_permissions(
                session, user_id=auth.user_id, role=auth.user_role
            )
        if key not in perms:
            raise HTTPException(status_code=403, detail="Permissão insuficiente")
        return auth

    return _dep
