# apps/api/src/agent/skills/buscar_conhecimento/use_case.py
from __future__ import annotations

import contextlib

from agent.skills.buscar_conhecimento.keyword_extractor import extract_keywords
from agent.skills.buscar_conhecimento.synonym_expander import expand_synonyms
from shared.domain.ports.knowledge import KnowledgePort


class BuscarConhecimento:
    def __init__(self, knowledge_repo: KnowledgePort, usage_log_repo: object) -> None:
        self._knowledge = knowledge_repo
        self._usage_log = usage_log_repo

    async def execute(self, query: str, account_id: int) -> dict:
        # Tentativa 1: query exata
        chunks = await self._knowledge.search(query=query, account_id=account_id)
        if chunks:
            await self._log(account_id, query, strategy="exact", found=True)
            return {"encontrado": True, "chunks": [c.text for c in chunks], "strategy": "exact"}

        # Tentativa 2: expansão de sinônimos
        keywords = extract_keywords(query)
        expanded = expand_synonyms(keywords)
        expanded_query = " ".join(expanded)
        chunks = await self._knowledge.search(query=expanded_query, account_id=account_id)
        if chunks:
            await self._log(account_id, query, strategy="synonyms", found=True)
            return {"encontrado": True, "chunks": [c.text for c in chunks], "strategy": "synonyms"}

        # Tentativa 3: keywords isoladas
        if keywords:
            keyword_query = " ".join(keywords)
            chunks = await self._knowledge.search(query=keyword_query, account_id=account_id)
            if chunks:
                await self._log(account_id, query, strategy="keywords", found=True)
                return {
                    "encontrado": True,
                    "chunks": [c.text for c in chunks],
                    "strategy": "keywords",
                }

        await self._log(account_id, query, strategy="all_failed", found=False)
        return {"encontrado": False, "chunks": [], "strategy": "all_failed"}

    async def _log(self, account_id: int, query: str, strategy: str, found: bool) -> None:
        if self._usage_log:
            with contextlib.suppress(Exception):
                await self._usage_log.registrar(
                    account_id=account_id, query=query, strategy=strategy, found=found
                )
