from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from interface.http.deps.admin_auth import AdminAuth, require_admin_role
from shared.adapters.db.repositories.profile_repo import ProfileRepository
from shared.adapters.db.session import session_scope
from shared.config.single_tenant import get_default_account_uuid
from shared.domain.entities.profile import Profile
from shared.domain.permissions.catalog import PERMISSION_CATALOG, all_permission_keys

router = APIRouter(tags=["admin-profiles"])


# --------------------------------------------------------------------------- #
# Schemas
# --------------------------------------------------------------------------- #
class ProfileListItem(BaseModel):
    id: str
    name: str
    is_system: bool
    permission_count: int
    user_count: int


class ProfileDetail(BaseModel):
    id: str
    name: str
    is_system: bool
    permissions: list[str]


class CreateProfileRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    permissions: list[str] = Field(default_factory=list)


class UpdateProfileRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    permissions: list[str] = Field(default_factory=list)


class PermissionItem(BaseModel):
    key: str
    action: str
    label: str


class PermissionGroup(BaseModel):
    module: str
    permissions: list[PermissionItem]


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _validate_permissions(permissions: list[str]) -> None:
    valid = set(all_permission_keys())
    invalid = [p for p in permissions if p not in valid]
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"unknown permission key(s): {', '.join(invalid)}",
        )


def _to_detail(profile: Profile) -> ProfileDetail:
    return ProfileDetail(
        id=str(profile.id),
        name=profile.name,
        is_system=profile.is_system,
        permissions=list(profile.permissions),
    )


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #
@router.get("/profiles", response_model=list[ProfileListItem])
async def list_profiles(
    auth: AdminAuth = Depends(require_admin_role),
) -> list[ProfileListItem]:
    async with session_scope() as session:
        account_uuid = await get_default_account_uuid(session)
        repo = ProfileRepository(session=session)
        rows = await repo.list_with_counts(account_uuid)
    return [
        ProfileListItem(
            id=str(r["id"]),
            name=str(r["name"]),
            is_system=bool(r["is_system"]),
            permission_count=int(r["permission_count"]),  # type: ignore[call-overload]
            user_count=int(r["user_count"]),  # type: ignore[call-overload]
        )
        for r in rows
    ]


@router.get("/profiles/{profile_id}", response_model=ProfileDetail)
async def get_profile(
    profile_id: str,
    auth: AdminAuth = Depends(require_admin_role),
) -> ProfileDetail:
    pid = _parse_uuid(profile_id)
    async with session_scope() as session:
        account_uuid = await get_default_account_uuid(session)
        repo = ProfileRepository(session=session)
        profile = await repo.get_by_id(account_uuid, pid)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="profile not found")
    return _to_detail(profile)


@router.post("/profiles", response_model=ProfileDetail, status_code=status.HTTP_201_CREATED)
async def create_profile(
    body: CreateProfileRequest,
    auth: AdminAuth = Depends(require_admin_role),
) -> ProfileDetail:
    _validate_permissions(body.permissions)
    async with session_scope() as session:
        account_uuid = await get_default_account_uuid(session)
        repo = ProfileRepository(session=session)
        if await repo.get_by_name(account_uuid, body.name) is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="profile with this name already exists",
            )
        profile = await repo.create(
            account_id=account_uuid,
            name=body.name,
            is_system=False,
            permissions=body.permissions,
        )
    return _to_detail(profile)


@router.put("/profiles/{profile_id}", response_model=ProfileDetail)
async def update_profile(
    profile_id: str,
    body: UpdateProfileRequest,
    auth: AdminAuth = Depends(require_admin_role),
) -> ProfileDetail:
    pid = _parse_uuid(profile_id)
    _validate_permissions(body.permissions)
    async with session_scope() as session:
        account_uuid = await get_default_account_uuid(session)
        repo = ProfileRepository(session=session)
        existing = await repo.get_by_id(account_uuid, pid)
        if existing is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="profile not found")
        if existing.is_system:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="system profiles cannot be edited",
            )
        clash = await repo.get_by_name(account_uuid, body.name)
        if clash is not None and clash.id != pid:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="profile with this name already exists",
            )
        profile = await repo.update(
            account_id=account_uuid,
            profile_id=pid,
            name=body.name,
            permissions=body.permissions,
        )
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="profile not found")
    return _to_detail(profile)


@router.delete("/profiles/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_profile(
    profile_id: str,
    auth: AdminAuth = Depends(require_admin_role),
) -> None:
    pid = _parse_uuid(profile_id)
    async with session_scope() as session:
        account_uuid = await get_default_account_uuid(session)
        repo = ProfileRepository(session=session)
        existing = await repo.get_by_id(account_uuid, pid)
        if existing is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="profile not found")
        if existing.is_system:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="system profiles cannot be deleted",
            )
        await repo.delete(account_uuid, pid)


@router.get("/permissions/catalog", response_model=list[PermissionGroup])
async def permissions_catalog(
    auth: AdminAuth = Depends(require_admin_role),
) -> list[PermissionGroup]:
    # Agrupa por módulo preservando a ordem de aparição em PERMISSION_CATALOG.
    groups: dict[str, list[PermissionItem]] = {}
    order: list[str] = []
    for perm in PERMISSION_CATALOG:
        if perm.module not in groups:
            groups[perm.module] = []
            order.append(perm.module)
        groups[perm.module].append(
            PermissionItem(key=perm.key, action=perm.action, label=perm.label)
        )
    return [PermissionGroup(module=m, permissions=groups[m]) for m in order]


def _parse_uuid(value: str) -> UUID:
    try:
        return UUID(value)
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="profile not found"
        ) from exc
