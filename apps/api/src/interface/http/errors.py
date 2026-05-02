from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from shared.adapters.observability.logger import get_logger
from shared.domain.errors import DomainError, TenantIsolationError

log = get_logger(__name__)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(TenantIsolationError)
    async def _tenant_iso(_request: Request, exc: TenantIsolationError) -> JSONResponse:
        log.error("tenant_isolation_error", error=str(exc))
        return JSONResponse(status_code=500, content={"error": "internal"})

    @app.exception_handler(DomainError)
    async def _domain(_request: Request, exc: DomainError) -> JSONResponse:
        log.warning("domain_error", error=str(exc))
        return JSONResponse(status_code=400, content={"error": str(exc)})

    @app.exception_handler(Exception)
    async def _unhandled(_request: Request, exc: Exception) -> JSONResponse:
        if isinstance(exc, (HTTPException, RequestValidationError)):
            raise exc
        log.exception("unhandled_error", error=str(exc))
        return JSONResponse(status_code=500, content={"error": "internal"})
