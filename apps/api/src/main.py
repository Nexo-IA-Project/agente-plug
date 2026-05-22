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
    webhook_message,
    webhook_purchase,
)
from interface.http.routers.admin import api_tokens as admin_api_tokens
from interface.http.routers.admin import auth as admin_auth
from interface.http.routers.admin import dlq as admin_dlq
from interface.http.routers.admin import documents as admin_documents
from interface.http.routers.admin import followup as admin_followup
from interface.http.routers.admin import (
    followup_enrollments as admin_followup_enrollments,
)
from interface.http.routers.admin import meta_templates as admin_meta_templates
from interface.http.routers.admin import products as admin_products
from interface.http.routers.admin import search as admin_search
from interface.http.routers.admin import settings as admin_settings
from shared.adapters.db.queue import PostgresJobQueue
from shared.adapters.db.repositories.webhook_event import WebhookEventRepository
from shared.adapters.db.session import get_sessionmaker
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

    def _event_repo_factory() -> WebhookEventRepository:
        session = get_sessionmaker()()
        return WebhookEventRepository(session)

    async def _validate_token(raw_token: str) -> bool:
        from shared.adapters.db.repositories.api_token_repo import ApiTokenRepository

        async with get_sessionmaker()() as session:
            repo = ApiTokenRepository(session)
            return await repo.validate(raw_token=raw_token)

    webhook_purchase.configure(
        dedup=dedup,
        event_repo_factory=_event_repo_factory,
        queue=queue,
        expected_token=settings.hubla_webhook_secret,
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
    app.include_router(webhook_message.router)
    app.include_router(admin_api_tokens.router, prefix="/admin")
    app.include_router(admin_auth.router, prefix="/admin")
    app.include_router(admin_documents.router, prefix="/admin")
    app.include_router(admin_search.router, prefix="/admin")
    app.include_router(admin_dlq.router, prefix="/admin")
    app.include_router(admin_settings.router, prefix="/admin")
    app.include_router(admin_followup.router, prefix="/admin")
    app.include_router(admin_followup_enrollments.router, prefix="/admin")
    app.include_router(admin_meta_templates.router, prefix="/admin")
    app.include_router(admin_products.router, prefix="/admin")
    return app


app = create_app()
