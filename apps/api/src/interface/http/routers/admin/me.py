from __future__ import annotations

import base64

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, EmailStr, Field

from interface.http.deps.admin_auth import AdminAuth, require_admin
from shared.adapters.db.repositories.user_repo import UserRepository
from shared.adapters.db.session import session_scope
from shared.application.use_cases.admin.change_my_password import (
    ChangeMyPasswordUseCase,
    InvalidCurrentPasswordError,
)

router = APIRouter(tags=["admin-me"])


class MeResponse(BaseModel):
    id: str
    name: str
    email: EmailStr
    role: str
    must_change_password: bool
    has_avatar: bool


class UpdateMeRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class UpdateAvatarRequest(BaseModel):
    data: str  # base64-encoded JPEG


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


@router.get("/me", response_model=MeResponse)
async def get_me(auth: AdminAuth = Depends(require_admin)) -> MeResponse:
    async with session_scope() as s:
        repo = UserRepository(s)
        user = await repo.get_by_id(auth.user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        return MeResponse(
            id=user.id,
            name=user.name,
            email=user.email,
            role=user.role.value,
            must_change_password=user.must_change_password,
            has_avatar=user.avatar is not None,
        )


@router.put("/me", response_model=MeResponse)
async def update_me(
    body: UpdateMeRequest,
    auth: AdminAuth = Depends(require_admin),
) -> MeResponse:
    async with session_scope() as s:
        repo = UserRepository(s)
        await repo.update_profile(user_id=auth.user_id, name=body.name)
        await s.commit()
        user = await repo.get_by_id(auth.user_id)
        return MeResponse(
            id=user.id, name=user.name, email=user.email, role=user.role.value,
            must_change_password=user.must_change_password,
            has_avatar=user.avatar is not None,
        )


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
        repo = UserRepository(s)
        await repo.update_avatar(user_id=auth.user_id, avatar=avatar_bytes)
        await s.commit()


@router.get("/me/avatar")
async def get_avatar(auth: AdminAuth = Depends(require_admin)) -> Response:
    async with session_scope() as s:
        repo = UserRepository(s)
        user = await repo.get_by_id(auth.user_id)
        if user is None or user.avatar is None:
            raise HTTPException(status_code=404, detail="No avatar")
        return Response(content=user.avatar, media_type="image/jpeg")


@router.put("/me/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    body: ChangePasswordRequest,
    auth: AdminAuth = Depends(require_admin),
) -> None:
    async with session_scope() as s:
        repo = UserRepository(s)
        uc = ChangeMyPasswordUseCase(user_repo=repo)
        try:
            await uc.execute(
                user_id=auth.user_id,
                current_password=body.current_password,
                new_password=body.new_password,
            )
        except InvalidCurrentPasswordError as e:
            raise HTTPException(status_code=401, detail=str(e)) from e
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e
        await s.commit()
