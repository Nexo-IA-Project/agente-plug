"""Repository para meta_template_media — storage de mídia de template no Postgres."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.adapters.db.models import MetaTemplateMediaModel


class MetaTemplateMediaRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, media_id: UUID) -> MetaTemplateMediaModel | None:
        result = await self._session.execute(
            select(MetaTemplateMediaModel).where(MetaTemplateMediaModel.id == media_id)
        )
        return result.scalar_one_or_none()

    async def get_by_sha(self, *, account_id: UUID, sha256: str) -> MetaTemplateMediaModel | None:
        result = await self._session.execute(
            select(MetaTemplateMediaModel)
            .where(MetaTemplateMediaModel.account_id == account_id)
            .where(MetaTemplateMediaModel.sha256 == sha256)
        )
        return result.scalar_one_or_none()

    async def insert(
        self,
        *,
        account_id: UUID,
        kind: str,
        mime: str,
        sha256: str,
        size_bytes: int,
        data: bytes,
        original_filename: str | None,
    ) -> MetaTemplateMediaModel:
        model = MetaTemplateMediaModel(
            account_id=account_id,
            kind=kind,
            mime=mime,
            sha256=sha256,
            size_bytes=size_bytes,
            data=data,
            original_filename=original_filename,
        )
        self._session.add(model)
        await self._session.flush()
        return model
