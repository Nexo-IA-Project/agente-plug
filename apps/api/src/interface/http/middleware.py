from __future__ import annotations

import asyncio
import contextvars
import re
import uuid
from uuid import UUID, uuid4

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from shared.adapters.db.repositories.audit_repo import SqlAuditRepository
from shared.adapters.geo.ip_api import IpApiGeoService
from shared.adapters.observability.logger import bind_context, reset_context
from shared.adapters.observability.logger import get_logger as _get_audit_log
from shared.domain.entities.audit_event import AuditEvent

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


_audit_log = _get_audit_log(__name__)
_background_tasks: set[asyncio.Task] = set()  # evita GC das tasks de geo lookup

# (method, path_regex, label, resource_type)
_ACTION_RULES: list[tuple[str, re.Pattern[str], str, str]] = [
    ("POST",   re.compile(r"^/admin/users/[^/]+/reset-password$"), "Resetou senha de usuário", "user"),
    ("POST",   re.compile(r"^/admin/users$"),                      "Criou usuário",            "user"),
    ("PUT",    re.compile(r"^/admin/users/[^/]+$"),                "Editou usuário",           "user"),
    ("DELETE", re.compile(r"^/admin/users/[^/]+$"),                "Excluiu usuário",          "user"),
    ("PUT",    re.compile(r"^/admin/me/password$"),                "Alterou própria senha",    "user"),
    ("PUT",    re.compile(r"^/admin/me/avatar$"),                  "Alterou avatar",           "user"),
    ("PUT",    re.compile(r"^/admin/me$"),                         "Editou perfil próprio",    "user"),
    ("POST",   re.compile(r"^/admin/products$"),                   "Criou produto",            "product"),
    ("PUT",    re.compile(r"^/admin/products/[^/]+$"),             "Editou produto",           "product"),
    ("DELETE", re.compile(r"^/admin/products/[^/]+$"),             "Excluiu produto",          "product"),
    ("POST",   re.compile(r"^/admin/documents/upload$"),           "Enviou documento KB",      "document"),
    ("DELETE", re.compile(r"^/admin/documents/[^/]+$"),            "Excluiu documento KB",     "document"),
    ("POST",   re.compile(r"^/admin/followup/flows/[^/]+/steps$"), "Adicionou step ao flow",   "flow_step"),
    ("PUT",    re.compile(r"^/admin/followup/flows/[^/]+/steps/[^/]+$"), "Editou step do flow",    "flow_step"),
    ("DELETE", re.compile(r"^/admin/followup/flows/[^/]+/steps/[^/]+$"), "Excluiu step do flow",   "flow_step"),
    ("PATCH",  re.compile(r"^/admin/followup/flows/[^/]+/steps/reorder$"), "Reordenou steps do flow", "flow_step"),
    ("POST",   re.compile(r"^/admin/followup/flows$"),             "Criou flow de follow-up",  "flow"),
    ("PUT",    re.compile(r"^/admin/followup/flows/[^/]+$"),       "Editou flow de follow-up", "flow"),
    ("DELETE", re.compile(r"^/admin/followup/flows/[^/]+$"),       "Excluiu flow de follow-up","flow"),
    ("POST",   re.compile(r"^/admin/meta-templates$"),             "Criou template Meta",      "meta_template"),
    ("DELETE", re.compile(r"^/admin/meta-templates/[^/]+$"),       "Excluiu template Meta",    "meta_template"),
    ("PUT",    re.compile(r"^/admin/settings$"),                   "Editou configurações",     "settings"),
    ("PUT",    re.compile(r"^/admin/smtp-config$"),                "Editou configuração SMTP", "settings"),
    ("POST",   re.compile(r"^/admin/api-tokens$"),                 "Criou token de API",       "api_token"),
    ("DELETE", re.compile(r"^/admin/api-tokens/[^/]+$"),           "Revogou token de API",     "api_token"),
    ("POST",   re.compile(r"^/admin/profiles$"),                   "Criou perfil",             "profile"),
    ("PUT",    re.compile(r"^/admin/profiles/[^/]+$"),             "Editou perfil",            "profile"),
    ("DELETE", re.compile(r"^/admin/profiles/[^/]+$"),             "Excluiu perfil",           "profile"),
    ("POST",   re.compile(r"^/admin/dlq/requeue-all$"),            "Reprocessou todos os jobs DLQ", "dlq"),
    ("POST",   re.compile(r"^/admin/dlq/[^/]+/requeue$"),          "Reprocessou job DLQ",      "dlq"),
    ("DELETE", re.compile(r"^/admin/dlq/[^/]+$"),                  "Excluiu job DLQ",          "dlq"),
]

_WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def resolve_audit_action(method: str, path: str) -> tuple[str, str] | None:
    """Returns (label, resource_type) or None if path should not be audited."""
    if method not in _WRITE_METHODS:
        return None
    for rule_method, pattern, label, resource_type in _ACTION_RULES:
        if method == rule_method and pattern.match(path):
            return label, resource_type
    return None


def _extract_ip(request: Request) -> str:
    cf = request.headers.get("CF-Connecting-IP")
    if cf:
        return cf.strip()
    fwd = request.headers.get("X-Forwarded-For")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else ""


def _extract_resource_id(path: str) -> str | None:
    parts = [p for p in path.split("/") if p]
    if len(parts) >= 2 and parts[-1] not in {"upload", "reorder", "requeue", "requeue-all"}:
        return parts[-1]
    return None


def _parse_uuid(value: str | None) -> UUID | None:
    if not value:
        return None
    try:
        return UUID(str(value))
    except (ValueError, TypeError):
        return None


async def _do_geo_update(event_id: UUID, ip: str) -> None:
    from shared.adapters.db.session import session_scope
    geo = IpApiGeoService()
    result = await geo.lookup(ip)
    if result is None:
        return
    async with session_scope() as session:
        repo = SqlAuditRepository(session=session)
        await repo.update_geo(event_id, city=result.city, country=result.country, region=result.region)


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)

        audit_ctx = getattr(request.state, "audit_ctx", None)
        if audit_ctx is None:
            return response

        action_result = resolve_audit_action(request.method, request.url.path)
        if action_result is None:
            return response

        label, resource_type = action_result
        ip = _extract_ip(request)
        resource_id = _extract_resource_id(request.url.path)

        account_id: UUID | None = _parse_uuid(str(audit_ctx.get("account_id", "")))
        if account_id is None:
            return response

        event_id = uuid4()
        user_email = audit_ctx.get("user_email", "")
        user_name = audit_ctx.get("user_name") or user_email or None
        event = AuditEvent(
            id=event_id,
            account_id=account_id,
            actor=user_email,
            user_id=audit_ctx.get("user_id") or None,
            user_name=user_name,
            action=label,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=ip or None,
            geo_city=None,
            geo_country=None,
            geo_region=None,
        )

        try:
            from shared.adapters.db.session import session_scope
            async with session_scope() as session:
                repo = SqlAuditRepository(session=session)
                await repo.save(event)
            if ip:
                _geo_task = asyncio.create_task(_do_geo_update(event_id, ip))
                _geo_task.add_done_callback(_background_tasks.discard)
                _background_tasks.add(_geo_task)
        except Exception:
            _audit_log.warning("audit_save_failed", path=request.url.path)

        return response
