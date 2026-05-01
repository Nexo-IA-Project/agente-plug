# apps/api/src/agent/skills/buscar_aluno_cademi/skill.py
from __future__ import annotations

from typing import Type

from langchain_core.tools import BaseTool
from langgraph.config import get_config
from pydantic import BaseModel, ConfigDict

from agent.skills._utils import _load_instructions
from agent.skills.buscar_aluno_cademi.preconditions import PRECONDITIONS
from agent.skills.buscar_aluno_cademi.use_case import BuscarAlunoCademi


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid")
    phone: str


class BuscarAlunoCademiTool(BaseTool):
    name: str = "buscar_aluno_cademi"
    description: str = _load_instructions(__file__)
    args_schema: Type[BaseModel] = _Input

    _use_case: BuscarAlunoCademi

    def __init__(self, use_case: BuscarAlunoCademi) -> None:
        super().__init__()
        self._use_case = use_case

    def _run(self, phone: str) -> str:  # pragma: no cover
        raise NotImplementedError("Use async")

    async def _arun(self, phone: str) -> str:
        cfg = get_config()["configurable"]
        account_id: str = cfg["account_id"]

        for pre in PRECONDITIONS:
            if not pre.passed:
                return pre.block_message

        result = await self._use_case.execute(phone=phone, account_id=account_id)
        if not result["encontrado"]:
            return result["mensagem"]
        return (
            f"Aluno encontrado: {result['nome']} ({result['email']}). "
            f"Cursos ativos: {', '.join(result['cursos']) or 'nenhum'}."
        )
