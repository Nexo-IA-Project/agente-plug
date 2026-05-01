from __future__ import annotations

from typing import Any, Type

from langchain_core.tools import BaseTool
from langgraph.config import get_config
from pydantic import BaseModel, ConfigDict

from shared.application.use_cases.knowledge.buscar_conhecimento import BuscarConhecimento
from shared.application.use_cases.knowledge.buscar_conhecimento_com_contexto import (
    BuscarConhecimentoComContexto,
)
from shared.application.use_cases.knowledge.keyword_extractor import KeywordExtractor
from shared.application.use_cases.knowledge.synonym_expander import SynonymExpander
from shared.domain.ports.chatnexo import ChatNexoPort
from shared.domain.ports.knowledge import KnowledgePort


class BuscarConhecimentoInput(BaseModel):
    query: str


class BuscarConhecimentoTool(BaseTool):
    name: str = "buscar_conhecimento"
    description: str = (
        "Busca resposta na base de conhecimento do produto (3 estratégias em cascata).\n"
        "Use quando: aluno faz pergunta técnica ou geral sobre o produto/plataforma.\n"
        "Retorna: chunks relevantes formatados OU \"ASK_CONTEXT: ...\" para pedir mais detalhes.\n"
        "Não use quando: dúvida é sobre reembolso, acesso ou loja express."
    )
    args_schema: Type[BaseModel] = BuscarConhecimentoInput

    buscar_uc: Any

    model_config = ConfigDict(arbitrary_types_allowed=True)

    async def _arun(self, query: str) -> str:
        cfg = get_config()["configurable"]
        result = await self.buscar_uc.execute(query=query, account_id=cfg["account_id"])
        if result.status == "found":
            return "\n\n---\n\n".join(c.text for c in result.chunks)
        return "ASK_CONTEXT: Me conta um pouco mais sobre o que você está precisando."

    def _run(self, **_: object) -> str:
        raise NotImplementedError


class BuscarConhecimentoComContextoInput(BaseModel):
    original_query: str
    context: str


class BuscarConhecimentoComContextoTool(BaseTool):
    name: str = "buscar_conhecimento_com_contexto"
    description: str = (
        "4ª tentativa de busca com contexto adicional fornecido pelo aluno.\n"
        "Use quando: buscar_conhecimento retornou ASK_CONTEXT e o aluno respondeu com mais detalhes.\n"
        "Retorna: chunks relevantes formatados OU sinaliza escalação para humano."
    )
    args_schema: Type[BaseModel] = BuscarConhecimentoComContextoInput

    contexto_uc: Any

    model_config = ConfigDict(arbitrary_types_allowed=True)

    async def _arun(self, original_query: str, context: str) -> str:
        cfg = get_config()["configurable"]
        result = await self.contexto_uc.execute(
            original_query=original_query,
            context=context,
            account_id=cfg["account_id"],
            conversation_id=cfg.get("conversation_id", ""),
        )
        if result.status == "found":
            return "\n\n---\n\n".join(c.text for c in result.chunks)
        return "ESCALATED: Transferindo para atendimento humano — não encontrei resposta na base de conhecimento."

    def _run(self, **_: object) -> str:
        raise NotImplementedError


def make_knowledge_skills(
    knowledge_repo: KnowledgePort,
    usage_log_repo: Any,
    chatnexo: ChatNexoPort,
) -> list[BaseTool]:
    expander = SynonymExpander()
    extractor = KeywordExtractor()
    return [
        BuscarConhecimentoTool(
            buscar_uc=BuscarConhecimento(knowledge_repo, expander, extractor),
        ),
        BuscarConhecimentoComContextoTool(
            contexto_uc=BuscarConhecimentoComContexto(knowledge_repo, usage_log_repo, chatnexo),
        ),
    ]
