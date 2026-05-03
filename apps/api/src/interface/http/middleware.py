from __future__ import annotations

import contextvars
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from shared.adapters.observability.logger import bind_context, reset_context

correlation_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "correlation_id", default=""
)


_CID_LEN = 32


def _safe_cid(value: str | None) -> str:
    """Accept only 32-char hex strings from clients; generate a new one otherwise."""
    if value and len(value) == _CID_LEN and all(c in "0123456789abcdefABCDEF" for c in value):
        return value.lower()
    return uuid.uuid4().hex


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        cid = _safe_cid(request.headers.get("X-Correlation-Id"))
        token = correlation_id_var.set(cid)
        reset_context()
        bind_context(correlation_id=cid)
        try:
            response = await call_next(request)
        finally:
            correlation_id_var.reset(token)
        response.headers["X-Correlation-Id"] = cid
        return response
