from __future__ import annotations

from dataclasses import dataclass

import structlog

from nexoia.application.use_cases.knowledge.keyword_extractor import KeywordExtractor
from nexoia.application.use_cases.knowledge.synonym_expander import SynonymExpander
from nexoia.config.settings import get_settings
from nexoia.domain.ports.knowledge import KnowledgeChunk, KnowledgePort

log = structlog.get_logger(__name__)


@dataclass
class BuscaResult:
    chunks: list[KnowledgeChunk]
    status: str  # "found" | "ask_context" | "escalated"


class BuscarConhecimento:
    def __init__(
        self,
        knowledge_repo: KnowledgePort,
        synonym_expander: SynonymExpander,
        keyword_extractor: KeywordExtractor,
    ) -> None:
        self._knowledge_repo = knowledge_repo
        self._synonym_expander = synonym_expander
        self._keyword_extractor = keyword_extractor

    async def execute(self, query: str, account_id: int) -> BuscaResult:
        settings = get_settings()
        threshold = settings.kb_attempt_1_threshold
        top_k = settings.kb_top_k

        # Tentativa 1: query exata
        chunks = await self._knowledge_repo.search(query, account_id, threshold=threshold, top_k=top_k)
        if chunks:
            return BuscaResult(chunks=chunks, status="found")

        # Tentativa 2: expansão de sinônimos
        expanded = self._synonym_expander.expand(query)
        chunks = await self._knowledge_repo.search(expanded, account_id, threshold=threshold, top_k=top_k)
        if chunks:
            return BuscaResult(chunks=chunks, status="found")

        # Tentativa 3: extração de keywords
        keywords = " ".join(self._keyword_extractor.extract(query))
        if keywords:
            chunks = await self._knowledge_repo.search(keywords, account_id, threshold=threshold, top_k=top_k)
            if chunks:
                return BuscaResult(chunks=chunks, status="found")

        log.info("knowledge_ask_context", query=query, account_id=account_id)
        return BuscaResult(chunks=[], status="ask_context")
