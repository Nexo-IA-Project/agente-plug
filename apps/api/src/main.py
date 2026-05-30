from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from interface.http.errors import register_error_handlers
from interface.http.middleware import CorrelationIdMiddleware
from interface.http.routers import (
    health,
    metrics,
    public_media,
    webhook_hubla,
    webhook_message,
    webhook_purchase,
)
from interface.http.routers.admin import api_tokens as admin_api_tokens
from interface.http.routers.admin import auth as admin_auth
from interface.http.routers.admin import chatnexo_agents as admin_chatnexo_agents
from interface.http.routers.admin import dlq as admin_dlq
from interface.http.routers.admin import documents as admin_documents
from interface.http.routers.admin import leads as admin_leads
from interface.http.routers.admin import me as admin_me
from interface.http.routers.admin import meta_templates as admin_meta_templates
from interface.http.routers.admin import onboarding as admin_onboarding
from interface.http.routers.admin import (
    onboarding_enrollments as admin_onboarding_enrollments,
)
from interface.http.routers.admin import products as admin_products
from interface.http.routers.admin import search as admin_search
from interface.http.routers.admin import settings as admin_settings
from interface.http.routers.admin import smtp_config as admin_smtp
from interface.http.routers.admin import unmapped_products as admin_unmapped_products
from interface.http.routers.admin import users as admin_users
from shared.adapters.db.queue import PostgresJobQueue
from shared.adapters.db.repositories.webhook_event import WebhookEventRepository
from shared.adapters.db.session import get_sessionmaker, session_scope
from shared.adapters.observability.logger import configure_logging, get_logger
from shared.adapters.redis.client import get_redis
from shared.adapters.redis.dedup import RedisDedup
from shared.config.settings import get_settings

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(level=settings.log_level)
    log.info("app_starting", log_level=settings.log_level)

    redis = get_redis()
    dedup = RedisDedup(redis)
    queue = PostgresJobQueue(sessionmaker=get_sessionmaker())

    @asynccontextmanager
    async def _event_repo_factory() -> AsyncIterator[WebhookEventRepository]:
        # session_scope commita no exit e fecha a conexão. Antes a sessão era
        # raw (sem context manager) e o INSERT do webhook nunca commitava →
        # conexões ficavam `idle in transaction` penduradas (leak corrigido).
        async with session_scope() as session:
            yield WebhookEventRepository(session)

    async def _validate_token(raw_token: str) -> bool:
        from shared.adapters.db.repositories.api_token_repo import ApiTokenRepository

        async with get_sessionmaker()() as session:
            repo = ApiTokenRepository(session)
            return await repo.validate(raw_token=raw_token)

    async def _resolve_hubla_token() -> str:
        # Lê o secret do IntegrationConfig (tela de Settings); fallback pro .env.
        # AccountConfigRepository.get() já implementa esse fallback internamente.
        from cryptography.fernet import Fernet

        from shared.adapters.db.repositories.account_config_repo import (
            AccountConfigRepository,
        )
        from shared.config.single_tenant import get_default_account_uuid

        async with get_sessionmaker()() as session:
            repo = AccountConfigRepository(
                session=session,
                fernet=Fernet(settings.integration_credentials_key.encode()),
            )
            account_uuid = await get_default_account_uuid(session)
            config = await repo.get(account_id=account_uuid)
            return config.integration.hubla_webhook_secret or settings.hubla_webhook_secret

    webhook_purchase.configure(
        dedup=dedup,
        event_repo_factory=_event_repo_factory,
        queue=queue,
        token_resolver=_resolve_hubla_token,
    )
    webhook_hubla.configure(
        dedup=dedup,
        event_repo_factory=_event_repo_factory,
        queue=queue,
        token_resolver=_resolve_hubla_token,
    )
    webhook_message.configure(
        dedup=dedup,
        event_repo_factory=_event_repo_factory,
        queue=queue,
        token_validator=_validate_token,
    )

    yield
    log.info("app_stopping")
    await redis.aclose()


def create_app() -> FastAPI:
    app = FastAPI(title="nexoia-agent", version="0.1.0", lifespan=lifespan)
    settings = get_settings()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_origin_regex=settings.cors_origin_regex,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(CorrelationIdMiddleware)
    register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(metrics.router)
    app.include_router(webhook_purchase.router)
    app.include_router(webhook_hubla.router)
    app.include_router(webhook_message.router)
    app.include_router(admin_api_tokens.router, prefix="/admin")
    app.include_router(admin_auth.router, prefix="/admin")
    app.include_router(admin_documents.router, prefix="/admin")
    app.include_router(admin_search.router, prefix="/admin")
    app.include_router(admin_dlq.router, prefix="/admin")
    app.include_router(admin_settings.router, prefix="/admin")
    app.include_router(admin_onboarding.router, prefix="/admin")
    app.include_router(admin_onboarding_enrollments.router, prefix="/admin")
    app.include_router(admin_meta_templates.router, prefix="/admin")
    app.include_router(public_media.router)
    app.include_router(admin_products.router, prefix="/admin")
    app.include_router(admin_leads.router, prefix="/admin")
    app.include_router(admin_chatnexo_agents.router, prefix="/admin")
    app.include_router(admin_users.router, prefix="/admin")
    app.include_router(admin_me.router, prefix="/admin")
    app.include_router(admin_smtp.router, prefix="/admin")
    app.include_router(admin_unmapped_products.router, prefix="/admin")
    return app


app = create_app()
