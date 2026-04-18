from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class StudentAccess:
    auto_login_link: str
    product_name: str
    email: str


@runtime_checkable
class CademiPort(Protocol):
    async def fetch_student_access(
        self, *, email: str, product_id: str
    ) -> StudentAccess | None: ...
