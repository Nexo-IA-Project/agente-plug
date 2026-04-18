from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class CademiStudent:
    id: str
    name: str
    email: str
    phone: str | None


class CademiPort(Protocol):
    async def get_student_by_email(self, email: str) -> CademiStudent | None: ...
    async def get_student_by_cpf(self, cpf: str) -> CademiStudent | None: ...
    async def get_access_link(self, student_id: str, product_id: str) -> str: ...
