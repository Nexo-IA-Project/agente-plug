from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool, tool
from langgraph.config import get_config

from nexoia.application.use_cases.knowledge.buscar_conhecimento import BuscarConhecimento
from nexoia.application.use_cases.knowledge.buscar_conhecimento_com_contexto import (
    BuscarConhecimentoComContexto,
)
from nexoia.application.use_cases.knowledge.keyword_extractor import KeywordExtractor
from nexoia.application.use_cases.knowledge.synonym_expander import SynonymExpander
from nexoia.domain.ports.chatnexo import ChatNexoPort
from nexoia.domain.ports.knowledge import KnowledgePort


def make_knowledge_skills(
    knowledge_repo: KnowledgePort,
    usage_log_repo: Any,
    chatnexo: ChatNexoPort,
) -> list[BaseTool]:
    expander = SynonymExpander()
    extractor = KeywordExtractor()
    buscar_uc = BuscarConhecimento(knowledge_repo, expander, extractor)
    contexto_uc = BuscarConhecimentoComContexto(knowledge_repo, usage_log_repo, chatnexo)

    @tool
    async def buscar_conhecimento(query: str) -> str:
        """
        Busca resposta na base de conhecimento do produto (3 estratégias em cascata).
        Use quando: aluno faz pergunta técnica ou geral sobre o produto/plataforma.
        Retorna: chunks relevantes formatados OU "ASK_CONTEXT: ..." para pedir mais detalhes.
        Não use quando: dúvida é sobre reembolso, acesso ou loja express.
        """
        cfg = get_config()["configurable"]
        result = await buscar_uc.execute(query=query, account_id=cfg["account_id"])
        if result.status == "found":
            return "\n\n---\n\n".join(c.text for c in result.chunks)
        return "ASK_CONTEXT: Me conta um pouco mais sobre o que você está precisando."

    @tool
    async def buscar_conhecimento_com_contexto(original_query: str, context: str) -> str:
        """
        4ª tentativa de busca com contexto adicional fornecido pelo aluno.
        Use quando: buscar_conhecimento retornou ASK_CONTEXT e o aluno respondeu com mais detalhes.
        Retorna: chunks relevantes formatados OU sinaliza escalação para humano.
        """
        cfg = get_config()["configurable"]
        result = await contexto_uc.execute(
            original_query=original_query,
            context=context,
            account_id=cfg["account_id"],
            conversation_id=cfg.get("conversation_id", ""),
        )
        if result.status == "found":
            return "\n\n---\n\n".join(c.text for c in result.chunks)
        return "ESCALATED: Transferindo para atendimento humano — não encontrei resposta na base de conhecimento."

    return [buscar_conhecimento, buscar_conhecimento_com_contexto]
