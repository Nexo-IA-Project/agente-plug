from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(slots=True)
class GeoResult:
    city: str
    country: str
    region: str


class GeoService(Protocol):
    async def lookup(self, ip: str) -> GeoResult | None: ...
