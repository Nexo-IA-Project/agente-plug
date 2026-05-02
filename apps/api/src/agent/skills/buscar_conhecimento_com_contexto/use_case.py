# apps/api/src/agent/skills/buscar_conhecimento_com_contexto/use_case.py
from __future__ import annotations

import contextlib

from agent.skills.buscar_conhecimento.keyword_extractor import extract_keywords
from agent.skills.buscar_conhecimento.synonym_expander import expand_synonyms
from shared.domain.ports.knowledge import KnowledgePort


class BuscarConhecimentoComContexto:
    def __init__(self, knowledge_repo: KnowledgePort, usage_log_repo: object) -> None:
        self._knowledge = knowledge_repo
        self._usage_log = usage_log_repo

    async def execute(self, query: str, contexto_aluno: str, account_id: int) -> dict:
        enriched_query = f"{query} {contexto_aluno}".strip()

        # Tentativa 1: query enriquecida com contexto
        chunks = await self._knowledge.search(query=enriched_query, account_id=account_id)
        if chunks:
            await self._log(account_id, query, strategy="context_enriched", found=True)
            return {
                "encontrado": True,
                "chunks": [c.text for c in chunks],
                "strategy": "context_enriched",
                "escalar": False,
            }

        # Tentativa 2: keywords do contexto enriquecido
        keywords = extract_keywords(enriched_query)
        expanded = expand_synonyms(keywords)
        expanded_query = " ".join(expanded)
        chunks = await self._knowledge.search(query=expanded_query, account_id=account_id)
        if chunks:
            await self._log(account_id, query, strategy="context_keywords", found=True)
            return {
                "encontrado": True,
                "chunks": [c.text for c in chunks],
                "strategy": "context_keywords",
                "escalar": False,
            }

        await self._log(account_id, query, strategy="context_failed", found=False)
        return {
            "encontrado": False,
            "chunks": [],
            "strategy": "context_failed",
            "escalar": True,
        }

    async def _log(self, account_id: int, query: str, strategy: str, found: bool) -> None:
        if self._usage_log:
            with contextlib.suppress(Exception):
                await self._usage_log.registrar(
                    account_id=account_id, query=query, strategy=strategy, found=found
                )
