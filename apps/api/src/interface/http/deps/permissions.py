from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from interface.http.deps.admin_auth import AdminAuth, require_admin, require_admin_sse
from shared.adapters.db.models import MembershipModel, ProfilePermissionModel, UserModel
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


async def resolve_membership_permissions(
    session: AsyncSession, *, membership_id: str | None, role: str
) -> set[str]:
    if role == "admin":
        return set(all_permission_keys())
    if membership_id is None:
        return set()
    profile_id = (
        await session.execute(
            select(MembershipModel.profile_id).where(MembershipModel.id == membership_id)
        )
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


async def _check_permission(auth: AdminAuth, key: str) -> AdminAuth:
    if auth.user_role == "admin":
        return auth
    async with session_scope() as session:
        perms = await resolve_membership_permissions(
            session, membership_id=auth.membership_id, role=auth.user_role
        )
    if key not in perms:
        raise HTTPException(status_code=403, detail="Permissão insuficiente")
    return auth


def require_permission(key: str) -> Callable[..., Awaitable[AdminAuth]]:
    async def _dep(auth: AdminAuth = Depends(require_admin)) -> AdminAuth:
        return await _check_permission(auth, key)

    return _dep


def require_permission_sse(key: str) -> Callable[..., Awaitable[AdminAuth]]:
    """Variante SSE de :func:`require_permission`.

    Depende de :func:`require_admin_sse` (aceita JWT via query string ``?token=``)
    em vez de :func:`require_admin`, mantendo o mesmo bypass de admin e checagem
    de permissão por operador.
    """

    async def _dep(auth: AdminAuth = Depends(require_admin_sse)) -> AdminAuth:
        return await _check_permission(auth, key)

    return _dep
