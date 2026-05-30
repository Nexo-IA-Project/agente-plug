from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field

from interface.http.deps.admin_auth import AdminAuth, require_admin_role
from shared.adapters.db.repositories.platform_config_repo import PlatformConfigRepository
from shared.adapters.db.repositories.profile_repo import ProfileRepository
from shared.adapters.db.repositories.user_repo import UserRepository
from shared.adapters.db.session import session_scope
from shared.adapters.email.smtp_email_service import SmtpEmailService
from shared.application.use_cases.admin.create_user import CreateUserUseCase
from shared.application.use_cases.admin.reset_user_password import (
    ResetUserPasswordUseCase,
)
from shared.config.single_tenant import get_default_account_uuid
from shared.domain.entities.user import UserRole

router = APIRouter(tags=["admin-users"])


class UserResponse(BaseModel):
    id: str
    name: str
    email: EmailStr
    role: Literal["admin", "operator"]
    is_active: bool
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


def _to_response(user, profile_name: str | None = None) -> UserResponse:
    profile_id = getattr(user, "profile_id", None)
    return UserResponse(
        id=user.id,
        name=user.name,
        email=user.email,
        role=user.role.value if hasattr(user.role, "value") else user.role,
        is_active=user.is_active,
        must_change_password=user.must_change_password,
        has_avatar=user.avatar is not None,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
        profile_id=str(profile_id) if profile_id is not None else None,
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
    auth: AdminAuth = Depends(require_admin_role),
) -> UserListResponse:
    async with session_scope() as s:
        account_id = auth.account_id or await get_default_account_uuid(s)
        repo = UserRepository(s)
        items, total = await repo.list_by_account(account_id, page, page_size)
        name_map = await ProfileRepository(s).name_map(account_id)
        return UserListResponse(
            items=[
                _to_response(u, name_map.get(u.profile_id) if u.profile_id else None) for u in items
            ],
            total=total,
            page=page,
            page_size=page_size,
        )


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: CreateUserRequest,
    auth: AdminAuth = Depends(require_admin_role),
) -> UserResponse:
    async with session_scope() as s:
        account_id = auth.account_id or await get_default_account_uuid(s)
        user_repo = UserRepository(s)
        profile_name: str | None = None
        profile_id = _parse_profile_id(body.profile_id)
        if profile_id is not None:
            profile = await ProfileRepository(s).get_by_id(account_id, profile_id)
            if profile is None:
                raise HTTPException(status_code=400, detail="Profile not found in this account")
            profile_name = profile.name
        email_svc = SmtpEmailService(repo=PlatformConfigRepository(s))
        uc = CreateUserUseCase(user_repo=user_repo, email_service=email_svc)
        try:
            user = await uc.execute(
                account_id=account_id,
                name=body.name,
                email=body.email,
                role=UserRole(body.role),
                profile_id=profile_id,
            )
        except ValueError as e:
            raise HTTPException(status_code=409, detail=str(e)) from e
        await s.commit()
        return _to_response(user, profile_name)


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    body: UpdateUserRequest,
    auth: AdminAuth = Depends(require_admin_role),
) -> UserResponse:
    async with session_scope() as s:
        account_id = auth.account_id or await get_default_account_uuid(s)
        repo = UserRepository(s)
        user = await repo.get_by_id(user_id)
        if user is None or user.account_id != account_id:
            raise HTTPException(status_code=404, detail="User not found")

        if (user.role == UserRole.ADMIN and body.role != "admin") or (
            user.role == UserRole.ADMIN and not body.is_active
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

        await repo.update_admin_fields(
            user_id=user_id,
            name=body.name,
            role=UserRole(body.role),
            is_active=body.is_active,
            profile_id=profile_id,
        )
        await s.commit()
        updated = await repo.get_by_id(user_id)
        return _to_response(updated, profile_name)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    auth: AdminAuth = Depends(require_admin_role),
) -> None:
    if user_id == auth.user_id:
        raise HTTPException(status_code=409, detail="Cannot delete your own user")

    async with session_scope() as s:
        account_id = auth.account_id or await get_default_account_uuid(s)
        repo = UserRepository(s)
        user = await repo.get_by_id(user_id)
        if user is None or user.account_id != account_id:
            raise HTTPException(status_code=404, detail="User not found")
        if user.role == UserRole.ADMIN:
            admin_count = await repo.count_active_admins(account_id)
            if admin_count <= 1:
                raise HTTPException(status_code=409, detail="Cannot delete the last admin")
        await repo.delete(user_id)
        await s.commit()


@router.post("/users/{user_id}/reset-password", status_code=status.HTTP_204_NO_CONTENT)
async def reset_password(
    user_id: str,
    auth: AdminAuth = Depends(require_admin_role),
) -> None:
    async with session_scope() as s:
        account_id = auth.account_id or await get_default_account_uuid(s)
        user_repo = UserRepository(s)
        target = await user_repo.get_by_id(user_id)
        if target is None or target.account_id != account_id:
            raise HTTPException(status_code=404, detail="User not found")

        email_svc = SmtpEmailService(repo=PlatformConfigRepository(s))
        uc = ResetUserPasswordUseCase(user_repo=user_repo, email_service=email_svc)
        await uc.execute(account_id=account_id, user_id=user_id)
        await s.commit()
