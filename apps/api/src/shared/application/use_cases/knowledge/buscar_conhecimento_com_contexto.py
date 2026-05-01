from __future__ import annotations

from typing import Any

import structlog

from nexoia.application.use_cases.knowledge.buscar_conhecimento import BuscaResult
from nexoia.config.settings import get_settings
from nexoia.domain.ports.chatnexo import ChatNexoPort
from nexoia.domain.ports.knowledge import KnowledgePort

log = structlog.get_logger(__name__)


class BuscarConhecimentoComContexto:
    def __init__(
        self,
        knowledge_repo: KnowledgePort,
        usage_log_repo: Any,
        chatnexo: ChatNexoPort,
    ) -> None:
        self._knowledge_repo = knowledge_repo
        self._usage_log_repo = usage_log_repo
        self._chatnexo = chatnexo

    async def execute(
        self,
        original_query: str,
        context: str,
        account_id: int,
        conversation_id: str,
    ) -> BuscaResult:
        settings = get_settings()
        enriched = f"{original_query} {context}"
        chunks = await self._knowledge_repo.search(
            enriched,
            account_id,
            threshold=settings.kb_attempt_1_threshold,
            top_k=settings.kb_top_k,
        )
        if chunks:
            return BuscaResult(chunks=chunks, status="found")

        await self._usage_log_repo.record_no_result(account_id, original_query)
        await self._chatnexo.transfer_to_human(
            account_id=str(account_id),
            conversation_id=conversation_id,
            reason="knowledge_not_found",
        )
        log.warning(
            "knowledge_all_attempts_exhausted",
            query=original_query,
            account_id=account_id,
        )
        return BuscaResult(chunks=[], status="escalated")
