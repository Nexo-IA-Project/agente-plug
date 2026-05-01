from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CorrelationId:
    value: str

    @classmethod
    def new(cls) -> CorrelationId:
        return cls(value=uuid.uuid4().hex)

    def __str__(self) -> str:
        return self.value
