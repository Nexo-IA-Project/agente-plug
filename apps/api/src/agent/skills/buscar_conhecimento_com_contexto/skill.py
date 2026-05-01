# apps/api/src/agent/skills/buscar_conhecimento_com_contexto/skill.py
from __future__ import annotations

from typing import Type

from langchain_core.tools import BaseTool
from langgraph.config import get_config
from pydantic import BaseModel, ConfigDict

from agent.skills._utils import _load_instructions
from agent.skills.buscar_conhecimento_com_contexto.preconditions import PRECONDITIONS
from agent.skills.buscar_conhecimento_com_contexto.use_case import BuscarConhecimentoComContexto


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str
    contexto_aluno: str


class BuscarConhecimentoComContextoTool(BaseTool):
    name: str = "buscar_conhecimento_com_contexto"
    description: str = _load_instructions(__file__)
    args_schema: Type[BaseModel] = _Input

    _use_case: BuscarConhecimentoComContexto

    def __init__(self, use_case: BuscarConhecimentoComContexto) -> None:
        super().__init__()
        self._use_case = use_case

    def _run(self, query: str, contexto_aluno: str) -> str:  # pragma: no cover
        raise NotImplementedError("Use async")

    async def _arun(self, query: str, contexto_aluno: str) -> str:
        cfg = get_config()["configurable"]
        account_id: int = int(cfg["account_id"])

        for pre in PRECONDITIONS:
            if not pre.passed:
                return pre.block_message

        result = await self._use_case.execute(
            query=query, contexto_aluno=contexto_aluno, account_id=account_id
        )
        if not result["encontrado"]:
            if result.get("escalar"):
                return (
                    "Não encontrei informações suficientes na base de conhecimento. "
                    "Vou escalar para um especialista humano."
                )
            return "Não encontrei informações sobre este tópico mesmo com contexto adicional."
        return "\n\n".join(result["chunks"])
