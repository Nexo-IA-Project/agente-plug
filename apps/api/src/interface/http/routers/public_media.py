"""Endpoint público (sem auth) que serve mídia de template do nosso Postgres.

UUID gera entropia suficiente pra evitar enumeração. SHA256 garante imutabilidade
do conteúdo, então Cache-Control longo é seguro. Acessível por Meta, ChatNexo e
frontend pra preview no painel.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from shared.adapters.db.repositories.meta_template_media_repo import (
    MetaTemplateMediaRepository,
)
from shared.adapters.db.session import session_scope

router = APIRouter(tags=["public-media"])


@router.get("/public/media/{media_id}")
async def get_media(media_id: UUID) -> Response:
    async with session_scope() as session:
        repo = MetaTemplateMediaRepository(session=session)
        record = await repo.get_by_id(media_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Media not found")
    return Response(
        content=bytes(record.data),
        media_type=record.mime,
        headers={
            "Cache-Control": "public, max-age=31536000, immutable",
            "Content-Length": str(record.size_bytes),
        },
    )
