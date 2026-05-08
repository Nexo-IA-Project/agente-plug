from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class StorageObject:
    url: str
    object_key: str
    size: int
    sha256: str
    content_type: str


class StoragePort(Protocol):
    async def upload(
        self, *, key: str, data: bytes, content_type: str
    ) -> StorageObject: ...

    async def delete(self, *, key: str) -> None: ...

    async def head(self, *, key: str) -> StorageObject | None: ...

    async def download(self, *, key: str) -> bytes: ...
