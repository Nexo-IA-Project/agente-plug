from __future__ import annotations

from typing import Any

import structlog
from openai import AsyncOpenAI

from cryptography.fernet import Fernet

from agent.context import AgentContext
from agent.guards import GuardService, LegalMentionGuard, LoopDetectorGuard
from agent.runner import run_agent
from agent.skill_loader import Adapters, build_registry
from shared.adapters.cademi.client import CademiClient
from shared.adapters.chatnexo.client import ChatNexoClient
from shared.adapters.db.repositories.access_case_repo import AccessCaseRepository
from shared.adapters.db.repositories.account_config_repo import AccountConfigRepository
from shared.adapters.db.repositories.chunk_repo import ChunkRepository
from shared.adapters.db.repositories.refund_case_repo import RefundCaseRepository
from shared.adapters.db.repositories.usage_log_repo import UsageLogRepository
from shared.adapters.db.session import session_scope
from shared.adapters.hubla.client import HublaClient
from shared.adapters.kb.knowledge_adapter import EmbeddingsKnowledgeAdapter
from shared.adapters.redis.client import get_redis
from shared.adapters.redis.refund_mutex import RedisRefundMutex
from shared.config.settings import get_settings

log = structlog.get_logger(__name__)


class _NullLegalHistory:
    """Stub until a proper DB-backed LegalHistoryPort is implemented."""

    async def has_prior_refund_mention(
        self, *, account_id: int, contact_id: str, purchase_date: Any
    ) -> bool:
        return False


async def handle_message(payload: dict[str, Any]) -> None:
    account_id: int = int(payload["account_id"])
    phone: str = payload["contact_phone"]
    conversation_id: int = int(payload["conversation_id"])
    text: str = payload["text"]

    log.info(
        "message_job_started",
        account_id=account_id,
        phone=phone,
        conversation_id=conversation_id,
    )

    await _process_message(
        account_id=account_id,
        phone=phone,
        conversation_id=conversation_id,
        text=text,
    )

    log.info("message_job_done", account_id=account_id, conversation_id=conversation_id)


async def _process_message(
    *,
    account_id: int,
    phone: str,
    conversation_id: int,
    text: str,
) -> None:
    settings = get_settings()
    redis = get_redis()

    fernet = Fernet(settings.integration_credentials_key.encode())

    async with session_scope() as session:
        config_repo = AccountConfigRepository(session=session, fernet=fernet)
        account_config = await config_repo.get(account_id=account_id)

        openai_client = AsyncOpenAI(api_key=account_config.integration.openai_api_key)
        chatnexo = ChatNexoClient.from_account_config(account_config)
        cademi = CademiClient.from_account_config(account_config)
        hubla = HublaClient()
        refund_mutex = RedisRefundMutex(redis, ttl_seconds=settings.refund_mutex_ttl_seconds)

        knowledge_repo = EmbeddingsKnowledgeAdapter(
            chunk_repo=ChunkRepository(session),
            openai_client=openai_client,
            embedding_model=settings.kb_embedding_model,
        )
        adapters = Adapters(
            access_repo=AccessCaseRepository(session),
            cademi=cademi,
            chatnexo=chatnexo,
            refund_repo=RefundCaseRepository(session),
            hubla=hubla,
            legal_history=_NullLegalHistory(),
            refund_mutex=refund_mutex,
            knowledge_repo=knowledge_repo,
            usage_log_repo=UsageLogRepository(session),
        )
        registry = build_registry(adapters)
        guard_service = GuardService([LegalMentionGuard(), LoopDetectorGuard()])

        ctx = AgentContext(
            account_id=str(account_id),
            phone=phone,
            conversation_id=str(conversation_id),
            thread_id=f"{account_id}:{phone}",
        )
        reply = await run_agent(
            ctx=ctx,
            user_message=text,
            registry=registry,
            session=session,
            client=openai_client,
            guard_service=guard_service,
        )

    await chatnexo.send_message(
        account_id=account_id,
        conversation_id=conversation_id,
        text=reply,
    )
    log.info("message_reply_sent", account_id=account_id, conversation_id=conversation_id)
