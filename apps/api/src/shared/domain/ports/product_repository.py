from __future__ import annotations

from typing import Protocol
from uuid import UUID

from shared.domain.entities.product import Product


class ProductRepository(Protocol):
    async def list_by_account(self, account_id: UUID) -> list[Product]: ...
    async def find_by_id(self, product_id: UUID) -> Product | None: ...
    async def find_active_by_hubla_id(self, account_id: UUID, hubla_id: str) -> Product | None: ...
    async def create(
        self, *, account_id: UUID, name: str, hubla_id: str, is_active: bool = True
    ) -> Product: ...
    async def update(
        self,
        product_id: UUID,
        *,
        name: str | None = None,
        hubla_id: str | None = None,
        is_active: bool | None = None,
    ) -> Product | None: ...
    async def delete(self, product_id: UUID) -> bool: ...
    async def count_flows(self, product_id: UUID) -> int: ...
