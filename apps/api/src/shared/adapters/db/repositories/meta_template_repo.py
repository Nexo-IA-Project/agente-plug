from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.adapters.db.models import MetaTemplateModel


class MetaTemplateRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_by_account(self, account_id: UUID) -> list[MetaTemplateModel]:
        result = await self._session.execute(
            select(MetaTemplateModel)
            .where(MetaTemplateModel.account_id == account_id)
            .order_by(MetaTemplateModel.created_at.desc())
        )
        return list(result.scalars().all())

    async def get(self, template_id: UUID, account_id: UUID) -> MetaTemplateModel | None:
        result = await self._session.execute(
            select(MetaTemplateModel)
            .where(MetaTemplateModel.id == template_id)
            .where(MetaTemplateModel.account_id == account_id)
        )
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str, account_id: UUID) -> MetaTemplateModel | None:
        result = await self._session.execute(
            select(MetaTemplateModel)
            .where(MetaTemplateModel.name == name)
            .where(MetaTemplateModel.account_id == account_id)
        )
        return result.scalar_one_or_none()

    async def create(self, **fields: Any) -> MetaTemplateModel:
        model = MetaTemplateModel(**fields)
        self._session.add(model)
        await self._session.flush()
        return model

    async def update_status(
        self,
        template_id: UUID,
        *,
        status: str,
        rejection_reason: str | None = None,
    ) -> None:
        model = await self._session.get(MetaTemplateModel, template_id)
        if not model:
            return
        model.status = status
        model.rejection_reason = rejection_reason
        model.last_synced_at = datetime.now(UTC)
        await self._session.flush()

    async def update(
        self,
        *,
        template_id: UUID,
        components: list[dict[str, Any]] | None = None,
        category: str | None = None,
        media_url: str | None = None,
        media_kind: str | None = None,
    ) -> None:
        """Atualiza campos do template no banco. Apenas campos não-None são alterados."""
        model = await self._session.get(MetaTemplateModel, template_id)
        if model is None:
            return
        if components is not None:
            model.components = components
        if category is not None:
            model.category = category
        if media_url is not None:
            model.media_url = media_url
        if media_kind is not None:
            model.media_kind = media_kind
        model.updated_at = datetime.now(UTC)
        await self._session.flush()

    async def delete(self, template_id: UUID) -> None:
        model = await self._session.get(MetaTemplateModel, template_id)
        if model:
            await self._session.delete(model)
            await self._session.flush()

    async def find_pending(self, account_id: UUID) -> list[MetaTemplateModel]:
        result = await self._session.execute(
            select(MetaTemplateModel)
            .where(MetaTemplateModel.account_id == account_id)
            .where(MetaTemplateModel.status == "PENDING")
        )
        return list(result.scalars().all())
