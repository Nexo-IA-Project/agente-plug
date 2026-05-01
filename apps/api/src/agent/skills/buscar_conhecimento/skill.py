# apps/api/src/agent/skills/buscar_conhecimento/skill.py
from __future__ import annotations

from typing import Type

from langchain_core.tools import BaseTool
from langgraph.config import get_config
from pydantic import BaseModel, ConfigDict

from agent.skills._utils import _load_instructions
from agent.skills.buscar_conhecimento.preconditions import PRECONDITIONS
from agent.skills.buscar_conhecimento.use_case import BuscarConhecimento


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str


class BuscarConhecimentoTool(BaseTool):
    name: str = "buscar_conhecimento"
    description: str = _load_instructions(__file__)
    args_schema: Type[BaseModel] = _Input

    _use_case: BuscarConhecimento

    def __init__(self, use_case: BuscarConhecimento) -> None:
        super().__init__()
        self._use_case = use_case

    def _run(self, query: str) -> str:  # pragma: no cover
        raise NotImplementedError("Use async")

    async def _arun(self, query: str) -> str:
        cfg = get_config()["configurable"]
        account_id: int = int(cfg["account_id"])

        for pre in PRECONDITIONS:
            if not pre.passed:
                return pre.block_message

        result = await self._use_case.execute(query=query, account_id=account_id)
        if not result["encontrado"]:
            return "Não encontrei informações sobre este tópico na base de conhecimento."
        return "\n\n".join(result["chunks"])
