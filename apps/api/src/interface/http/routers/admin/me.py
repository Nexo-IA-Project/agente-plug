from __future__ import annotations

import base64
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from interface.http.deps.admin_auth import AdminAuth, require_admin
from interface.http.deps.permissions import resolve_membership_permissions
from shared.adapters.db.repositories.identity_repo import IdentityRepository
from shared.adapters.db.repositories.membership_repo import MembershipRepository
from shared.adapters.db.repositories.profile_repo import ProfileRepository
from shared.adapters.db.session import session_scope
from shared.application.use_cases.admin.change_my_password import (
    ChangeMyPasswordUseCase,
    InvalidCurrentPasswordError,
)

router = APIRouter(tags=["admin-me"])


class MembershipItem(BaseModel):
    account_id: str
    account_name: str
    role: str
    is_owner: bool
    is_current: bool


class MeResponse(BaseModel):
    id: str
    name: str
    email: EmailStr
    role: str
    must_change_password: bool
    has_avatar: bool
    profile_id: str | None = None
    profile_name: str | None = None
    permissions: list[str] = []


async def _resolve_profile_name(
    s: AsyncSession, auth: AdminAuth, profile_id: UUID | None
) -> str | None:
    """Resolve o nome do perfil do membership atual (scoped por account). None se sem perfil."""
    if profile_id is None or auth.account_id is None:
        return None
    names = await ProfileRepository(session=s).name_map(auth.account_id)
    return names.get(profile_id)


async def _profile_id_for_membership(s: AsyncSession, auth: AdminAuth) -> UUID | None:
    """O perfil pertence ao membership (escopo por conta), não à identidade."""
    if auth.membership_id is None:
        return None
    membership = await MembershipRepository(s).get_by_id(auth.membership_id)
    return membership.profile_id if membership else None


class UpdateMeRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class UpdateAvatarRequest(BaseModel):
    data: str  # base64-encoded JPEG


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


async def _build_me(s: AsyncSession, auth: AdminAuth) -> MeResponse:
    identity = await IdentityRepository(s).get_by_id(auth.identity_id)
    if identity is None:
        raise HTTPException(status_code=404, detail="Identity not found")
    perms = sorted(
        await resolve_membership_permissions(
            s, membership_id=auth.membership_id, role=auth.user_role
        )
    )
    profile_id = await _profile_id_for_membership(s, auth)
    return MeResponse(
        id=identity.id,
        name=identity.name,
        email=identity.email,
        role=auth.user_role,
        must_change_password=identity.must_change_password,
        has_avatar=identity.avatar is not None,
        profile_id=str(profile_id) if profile_id else None,
        profile_name=await _resolve_profile_name(s, auth, profile_id),
        permissions=perms,
    )


@router.get("/me", response_model=MeResponse)
async def get_me(auth: AdminAuth = Depends(require_admin)) -> MeResponse:
    async with session_scope() as s:
        return await _build_me(s, auth)


@router.put("/me", response_model=MeResponse)
async def update_me(
    body: UpdateMeRequest,
    auth: AdminAuth = Depends(require_admin),
) -> MeResponse:
    async with session_scope() as s:
        await IdentityRepository(s).update_profile(identity_id=auth.identity_id, name=body.name)
        await s.commit()
        return await _build_me(s, auth)


@router.put("/me/avatar", status_code=status.HTTP_204_NO_CONTENT)
async def update_avatar(
    body: UpdateAvatarRequest,
    auth: AdminAuth = Depends(require_admin),
) -> None:
    try:
        raw = body.data
        if "," in raw:
            raw = raw.split(",", 1)[1]
        avatar_bytes = base64.b64decode(raw, validate=True)
    except Exception as e:
        raise HTTPException(status_code=422, detail="Invalid base64 image") from e

    if len(avatar_bytes) > 200 * 1024:
        raise HTTPException(status_code=413, detail="Avatar exceeds 200KB after crop")

    async with session_scope() as s:
        await IdentityRepository(s).update_avatar(identity_id=auth.identity_id, avatar=avatar_bytes)
        await s.commit()


@router.get("/me/avatar")
async def get_avatar(auth: AdminAuth = Depends(require_admin)) -> Response:
    async with session_scope() as s:
        identity = await IdentityRepository(s).get_by_id(auth.identity_id)
        if identity is None or identity.avatar is None:
            raise HTTPException(status_code=404, detail="No avatar")
        return Response(content=identity.avatar, media_type="image/jpeg")


@router.put("/me/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    body: ChangePasswordRequest,
    auth: AdminAuth = Depends(require_admin),
) -> None:
    async with session_scope() as s:
        uc = ChangeMyPasswordUseCase(identity_repo=IdentityRepository(s))
        try:
            await uc.execute(
                identity_id=auth.identity_id,
                current_password=body.current_password,
                new_password=body.new_password,
            )
        except InvalidCurrentPasswordError as e:
            raise HTTPException(status_code=401, detail=str(e)) from e
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e
        await s.commit()


@router.get("/me/memberships", response_model=list[MembershipItem])
async def list_my_memberships(
    auth: AdminAuth = Depends(require_admin),
) -> list[MembershipItem]:
    async with session_scope() as s:
        views = await MembershipRepository(s).list_active_by_identity(auth.identity_id)
        return [
            MembershipItem(
                account_id=str(v.account_id),
                account_name=v.account_name,
                role=v.role.value,
                is_owner=v.is_owner,
                is_current=(str(v.account_id) == str(auth.account_id)),
            )
            for v in views
        ]
