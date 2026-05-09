from __future__ import annotations

from typing import Protocol
from uuid import UUID

from shared.domain.entities.course import Course


class CourseRepository(Protocol):
    async def list_by_account(self, account_id: UUID) -> list[Course]: ...
    async def find_by_id(self, course_id: UUID) -> Course | None: ...
    async def find_active_by_hubla_id(
        self, account_id: UUID, hubla_id: str
    ) -> Course | None: ...
    async def create(
        self,
        *,
        account_id: UUID,
        name: str,
        hubla_id: str,
        is_active: bool = True,
    ) -> Course: ...
    async def update(
        self,
        course_id: UUID,
        *,
        name: str | None = None,
        hubla_id: str | None = None,
        is_active: bool | None = None,
    ) -> Course | None: ...
    async def delete(self, course_id: UUID) -> bool: ...
    async def count_flows(self, course_id: UUID) -> int: ...
