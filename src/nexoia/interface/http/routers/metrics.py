from __future__ import annotations

from fastapi import APIRouter, Response

from nexoia.infrastructure.observability.metrics import CONTENT_TYPE, render_latest

router = APIRouter()


@router.get("/metrics")
async def metrics() -> Response:
    return Response(content=render_latest(), media_type=CONTENT_TYPE)
