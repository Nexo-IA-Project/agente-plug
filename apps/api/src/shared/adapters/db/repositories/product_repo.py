from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.adapters.db.models import OnboardingFlowModel, ProductModel
from shared.domain.entities.product import Product


def _to_entity(m: ProductModel) -> Product:
    return Product(
        id=m.id,
        account_id=m.account_id,
        name=m.name,
        hubla_id=m.hubla_id,
        is_active=m.is_active,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


@dataclass
class SqlProductRepository:
    session: AsyncSession

    async def list_by_account(self, account_id: UUID) -> list[Product]:
        stmt = (
            select(ProductModel)
            .where(ProductModel.account_id == account_id)
            .order_by(ProductModel.name)
        )
        rows = (await self.session.execute(stmt)).scalars().all()
        return [_to_entity(m) for m in rows]

    async def find_by_id(self, product_id: UUID) -> Product | None:
        m = await self.session.get(ProductModel, product_id)
        return _to_entity(m) if m else None

    async def find_active_by_hubla_id(self, account_id: UUID, hubla_id: str) -> Product | None:
        stmt = select(ProductModel).where(
            ProductModel.account_id == account_id,
            ProductModel.hubla_id == hubla_id,
            ProductModel.is_active.is_(True),
        )
        m = (await self.session.execute(stmt)).scalar_one_or_none()
        return _to_entity(m) if m else None

    async def create(
        self, *, account_id: UUID, name: str, hubla_id: str, is_active: bool = True
    ) -> Product:
        now = datetime.now(UTC)
        m = ProductModel(
            id=uuid4(),
            account_id=account_id,
            name=name,
            hubla_id=hubla_id,
            is_active=is_active,
            created_at=now,
            updated_at=now,
        )
        self.session.add(m)
        await self.session.flush()
        return _to_entity(m)

    async def update(
        self,
        product_id: UUID,
        *,
        name: str | None = None,
        hubla_id: str | None = None,
        is_active: bool | None = None,
    ) -> Product | None:
        m = await self.session.get(ProductModel, product_id)
        if m is None:
            return None
        if name is not None:
            m.name = name
        if hubla_id is not None:
            m.hubla_id = hubla_id
        if is_active is not None:
            m.is_active = is_active
        m.updated_at = datetime.now(UTC)
        await self.session.flush()
        return _to_entity(m)

    async def delete(self, product_id: UUID) -> bool:
        m = await self.session.get(ProductModel, product_id)
        if m is None:
            return False
        await self.session.delete(m)
        await self.session.flush()
        return True

    async def count_flows(self, product_id: UUID) -> int:
        stmt = select(func.count(OnboardingFlowModel.id)).where(
            OnboardingFlowModel.product_id == product_id
        )
        return int((await self.session.execute(stmt)).scalar_one())

    async def count_flows_bulk(self, product_ids: list[UUID]) -> dict[UUID, int]:
        """Conta flows por produto em UMA query única (evita N+1).

        Retorna dict {product_id: count}. Produtos sem flows não aparecem no dict
        (caller deve usar `.get(pid, 0)` para resolver defaults).
        """
        if not product_ids:
            return {}
        stmt = (
            select(
                OnboardingFlowModel.product_id,
                func.count(OnboardingFlowModel.id),
            )
            .where(OnboardingFlowModel.product_id.in_(product_ids))
            .group_by(OnboardingFlowModel.product_id)
        )
        rows = (await self.session.execute(stmt)).all()
        return {row[0]: int(row[1]) for row in rows}
