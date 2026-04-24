from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from nexoia.config.settings import get_settings
from nexoia.infrastructure.db.repositories.webhook_event import WebhookEventRepository
from nexoia.infrastructure.db.session import get_sessionmaker
from nexoia.infrastructure.observability.logger import configure_logging, get_logger
from nexoia.infrastructure.redis.client import get_redis
from nexoia.infrastructure.redis.dedup import RedisDedup
from nexoia.infrastructure.redis.queue import PriorityQueue
from nexoia.interface.http.errors import register_error_handlers
from nexoia.interface.http.middleware import CorrelationIdMiddleware
from nexoia.interface.http.routers import (
    health,
    metrics,
    webhook_message,
    webhook_purchase,
)

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(level=settings.log_level)
    log.info("app_starting", log_level=settings.log_level)

    redis = get_redis()
    dedup = RedisDedup(redis)
    queue = PriorityQueue(
        redis, name="jobs", priority_enabled=settings.enable_priority_queue
    )

    def _event_repo_factory() -> WebhookEventRepository:
        session = get_sessionmaker()()
        return WebhookEventRepository(session)

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
        expected_api_key=settings.chatnexo_api_key,
    )

    yield
    log.info("app_stopping")
    await redis.aclose()


def create_app() -> FastAPI:
    app = FastAPI(title="nexoia-agent", version="0.1.0", lifespan=lifespan)
    app.add_middleware(CorrelationIdMiddleware)
    register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(metrics.router)
    app.include_router(webhook_purchase.router)
    app.include_router(webhook_message.router)
    return app


app = create_app()
