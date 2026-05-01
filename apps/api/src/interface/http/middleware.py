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


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        cid = request.headers.get("X-Correlation-Id") or uuid.uuid4().hex
        token = correlation_id_var.set(cid)
        reset_context()
        bind_context(correlation_id=cid)
        try:
            response = await call_next(request)
        finally:
            correlation_id_var.reset(token)
        response.headers["X-Correlation-Id"] = cid
        return response
