from __future__ import annotations

import uuid as _uuid_module
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from interface.http.deps.admin_auth import AdminAuth, require_admin
from shared.adapters.db.models import AccountModel
from shared.adapters.db.repositories.course_repo import SqlCourseRepository
from shared.adapters.db.session import session_scope

router = APIRouter(tags=["admin-courses"])


class CreateCourseRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    hubla_id: str = Field(min_length=1, max_length=200)
    is_active: bool = True


class UpdateCourseRequest(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    hubla_id: str | None = Field(default=None, max_length=200)
    is_active: bool | None = None


class CourseResponse(BaseModel):
    id: UUID
    name: str
    hubla_id: str
    is_active: bool
    flow_count: int
    created_at: datetime
    updated_at: datetime


async def _get_account_uuid(session: object) -> _uuid_module.UUID:
    """Retorna o ID da primeira account (single-tenant na prática)."""
    result = await session.execute(select(AccountModel.id).limit(1))  # type: ignore[attr-defined]
    value: _uuid_module.UUID = result.scalar_one()
    return value


@router.get("/courses", response_model=list[CourseResponse])
async def list_courses(
    auth: AdminAuth = Depends(require_admin),  # noqa: B008
) -> list[CourseResponse]:
    async with session_scope() as session:
        account_uuid = await _get_account_uuid(session)
        repo = SqlCourseRepository(session=session)
        courses = await repo.list_by_account(account_uuid)
        items: list[CourseResponse] = []
        for c in courses:
            items.append(
                CourseResponse(
                    id=c.id,
                    name=c.name,
                    hubla_id=c.hubla_id,
                    is_active=c.is_active,
                    flow_count=await repo.count_flows(c.id),
                    created_at=c.created_at,
                    updated_at=c.updated_at,
                )
            )
    return items


@router.post(
    "/courses",
    response_model=CourseResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_course(
    body: CreateCourseRequest,
    auth: AdminAuth = Depends(require_admin),  # noqa: B008
) -> CourseResponse:
    async with session_scope() as session:
        account_uuid = await _get_account_uuid(session)
        repo = SqlCourseRepository(session=session)
        try:
            c = await repo.create(
                account_id=account_uuid,
                name=body.name,
                hubla_id=body.hubla_id,
                is_active=body.is_active,
            )
        except IntegrityError as exc:
            await session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="course with hubla_id already exists",
            ) from exc
    return CourseResponse(
        id=c.id,
        name=c.name,
        hubla_id=c.hubla_id,
        is_active=c.is_active,
        flow_count=0,
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


@router.put("/courses/{course_id}", response_model=CourseResponse)
async def update_course(
    course_id: UUID,
    body: UpdateCourseRequest,
    auth: AdminAuth = Depends(require_admin),  # noqa: B008
) -> CourseResponse:
    async with session_scope() as session:
        repo = SqlCourseRepository(session=session)
        try:
            c = await repo.update(
                course_id,
                name=body.name,
                hubla_id=body.hubla_id,
                is_active=body.is_active,
            )
        except IntegrityError as exc:
            await session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="course with hubla_id already exists",
            ) from exc
        if c is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="course not found",
            )
        flow_count = await repo.count_flows(c.id)
    return CourseResponse(
        id=c.id,
        name=c.name,
        hubla_id=c.hubla_id,
        is_active=c.is_active,
        flow_count=flow_count,
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


@router.delete("/courses/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_course(
    course_id: UUID,
    auth: AdminAuth = Depends(require_admin),  # noqa: B008
) -> None:
    async with session_scope() as session:
        repo = SqlCourseRepository(session=session)
        existing = await repo.find_by_id(course_id)
        if existing is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="course not found",
            )
        flow_count = await repo.count_flows(course_id)
        if flow_count > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"course has {flow_count} flow(s) linked",
            )
        await repo.delete(course_id)
