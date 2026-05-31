from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from interface.http.deps.admin_auth import AdminAuth
from interface.http.deps.permissions import require_permission
from shared.adapters.db.repositories.identity_repo import IdentityRepository
from shared.adapters.db.repositories.membership_repo import MembershipRepository, MemberView
from shared.adapters.db.repositories.platform_config_repo import PlatformConfigRepository
from shared.adapters.db.repositories.profile_repo import ProfileRepository
from shared.adapters.db.session import session_scope
from shared.adapters.email.smtp_email_service import SmtpEmailService
from shared.application.use_cases.admin.add_member import AddMemberUseCase
from shared.application.use_cases.admin.reset_user_password import (
    ResetUserPasswordUseCase,
)
from shared.config.single_tenant import get_default_account_uuid
from shared.domain.entities.membership import Membership
from shared.domain.entities.user import UserRole

router = APIRouter(tags=["admin-users"])

# Dependências de permissão como variáveis de módulo para permitir override em testes
# (a fábrica require_permission cria uma função nova a cada chamada).
_perm_view = require_permission("users.view")
_perm_manage = require_permission("users.manage")


class UserResponse(BaseModel):
    id: str
    name: str
    email: EmailStr
    role: Literal["admin", "operator"]
    is_active: bool
    is_owner: bool = False
    must_change_password: bool
    has_avatar: bool
    created_at: datetime
    last_login_at: datetime | None
    profile_id: str | None = None
    profile_name: str | None = None


class UserListResponse(BaseModel):
    items: list[UserResponse]
    total: int
    page: int
    page_size: int


class CreateUserRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    role: Literal["admin", "operator"]
    profile_id: str | None = None


class UpdateUserRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    role: Literal["admin", "operator"]
    is_active: bool
    profile_id: str | None = None


def _view_to_response(v: MemberView, profile_name: str | None = None) -> UserResponse:
    return UserResponse(
        id=v.membership_id,
        name=v.name,
        email=v.email,
        role=v.role.value if hasattr(v.role, "value") else v.role,
        is_active=v.is_active,
        is_owner=v.is_owner,
        must_change_password=v.must_change_password,
        has_avatar=v.has_avatar,
        created_at=v.created_at,
        last_login_at=v.last_login_at,
        profile_id=str(v.profile_id) if v.profile_id else None,
        profile_name=profile_name,
    )


def _parse_profile_id(raw: str | None) -> UUID | None:
    if raw is None or raw == "":
        return None
    try:
        return UUID(raw)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid profile_id") from e


@router.get("/users", response_model=UserListResponse)
async def list_users(
    page: int = 1,
    page_size: int = 50,
    auth: AdminAuth = Depends(_perm_view),
) -> UserListResponse:
    async with session_scope() as s:
        account_id = auth.account_id or await get_default_account_uuid(s)
        items, total = await MembershipRepository(s).list_by_account(account_id, page, page_size)
        name_map = await ProfileRepository(s).name_map(account_id)
        return UserListResponse(
            items=[
                _view_to_response(v, name_map.get(v.profile_id) if v.profile_id else None)
                for v in items
            ],
            total=total,
            page=page,
            page_size=page_size,
        )


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: CreateUserRequest,
    auth: AdminAuth = Depends(_perm_manage),
) -> UserResponse:
    async with session_scope() as s:
        account_id = auth.account_id or await get_default_account_uuid(s)
        profile_name: str | None = None
        profile_id = _parse_profile_id(body.profile_id)
        if profile_id is not None:
            profile = await ProfileRepository(s).get_by_id(account_id, profile_id)
            if profile is None:
                raise HTTPException(status_code=400, detail="Profile not found in this account")
            profile_name = profile.name
        email_svc = SmtpEmailService(repo=PlatformConfigRepository(s))
        uc = AddMemberUseCase(
            identity_repo=IdentityRepository(s),
            membership_repo=MembershipRepository(s),
            email_service=email_svc,
        )
        try:
            result = await uc.execute(
                account_id=account_id,
                name=body.name,
                email=body.email,
                role=UserRole(body.role),
                profile_id=profile_id,
            )
        except ValueError as e:
            raise HTTPException(status_code=409, detail=str(e)) from e
        await s.commit()
        return UserResponse(
            id=result.membership.id,
            name=result.identity.name,
            email=result.identity.email,
            role=body.role,
            is_active=result.membership.is_active,
            is_owner=result.membership.is_owner,
            must_change_password=result.identity.must_change_password,
            has_avatar=result.identity.avatar is not None,
            created_at=result.membership.created_at,
            last_login_at=result.identity.last_login_at,
            profile_id=str(profile_id) if profile_id else None,
            profile_name=profile_name,
        )


async def _load_membership(s: AsyncSession, membership_id: str, account_id: UUID) -> Membership:
    """Carrega o membership da conta e bloqueia o owner (gestão é da plataforma)."""
    membership = await MembershipRepository(s).get_by_id(membership_id)
    if membership is None or membership.account_id != account_id:
        raise HTTPException(status_code=404, detail="Membership not found")
    if membership.is_owner:
        raise HTTPException(
            status_code=403,
            detail="Owner protegido: somente a plataforma pode alterá-lo",
        )
    return membership


@router.put("/users/{membership_id}", response_model=UserResponse)
async def update_user(
    membership_id: str,
    body: UpdateUserRequest,
    auth: AdminAuth = Depends(_perm_manage),
) -> UserResponse:
    async with session_scope() as s:
        account_id = auth.account_id or await get_default_account_uuid(s)
        repo = MembershipRepository(s)
        membership = await _load_membership(s, membership_id, account_id)

        if (membership.role == UserRole.ADMIN and body.role != "admin") or (
            membership.role == UserRole.ADMIN and not body.is_active
        ):
            admin_count = await repo.count_active_admins(account_id)
            if admin_count <= 1:
                raise HTTPException(
                    status_code=409, detail="Cannot demote/deactivate the last admin"
                )

        profile_name: str | None = None
        profile_id = _parse_profile_id(body.profile_id)
        if profile_id is not None:
            profile = await ProfileRepository(s).get_by_id(account_id, profile_id)
            if profile is None:
                raise HTTPException(status_code=400, detail="Profile not found in this account")
            profile_name = profile.name

        identity_repo = IdentityRepository(s)
        await repo.update_fields(
            membership_id=membership_id,
            role=UserRole(body.role),
            is_active=body.is_active,
            profile_id=profile_id,
        )
        # O nome da pessoa pertence à identidade, não ao membership.
        await identity_repo.update_profile(membership.identity_id, body.name)
        await s.commit()

        identity = await identity_repo.get_by_id(membership.identity_id)
        return UserResponse(
            id=membership_id,
            name=body.name,
            email=identity.email if identity else auth.user_email,
            role=body.role,
            is_active=body.is_active,
            is_owner=membership.is_owner,
            must_change_password=identity.must_change_password if identity else False,
            has_avatar=identity.avatar is not None if identity else False,
            created_at=membership.created_at,
            last_login_at=identity.last_login_at if identity else None,
            profile_id=str(profile_id) if profile_id else None,
            profile_name=profile_name,
        )


@router.delete("/users/{membership_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    membership_id: str,
    auth: AdminAuth = Depends(_perm_manage),
) -> None:
    async with session_scope() as s:
        account_id = auth.account_id or await get_default_account_uuid(s)
        repo = MembershipRepository(s)
        membership = await _load_membership(s, membership_id, account_id)
        if membership.identity_id == auth.identity_id:
            raise HTTPException(status_code=409, detail="Cannot delete your own user")
        if membership.role == UserRole.ADMIN:
            admin_count = await repo.count_active_admins(account_id)
            if admin_count <= 1:
                raise HTTPException(status_code=409, detail="Cannot delete the last admin")
        await repo.delete(membership_id)
        await s.commit()


@router.post("/users/{membership_id}/reset-password", status_code=status.HTTP_204_NO_CONTENT)
async def reset_password(
    membership_id: str,
    auth: AdminAuth = Depends(_perm_manage),
) -> None:
    async with session_scope() as s:
        account_id = auth.account_id or await get_default_account_uuid(s)
        membership = await _load_membership(s, membership_id, account_id)

        email_svc = SmtpEmailService(repo=PlatformConfigRepository(s))
        uc = ResetUserPasswordUseCase(identity_repo=IdentityRepository(s), email_service=email_svc)
        await uc.execute(account_id=account_id, identity_id=membership.identity_id)
        await s.commit()
