# apps/api/src/agent/skills/verificar_caso_acesso/skill.py
from __future__ import annotations

from langchain_core.tools import BaseTool
from langgraph.config import get_config
from pydantic import BaseModel, ConfigDict

from agent.skills._utils import _load_instructions
from agent.skills.verificar_caso_acesso.preconditions import PRECONDITIONS
from agent.skills.verificar_caso_acesso.use_case import VerificarCasoAcesso


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str


class VerificarCasoAcessoTool(BaseTool):
    name: str = "verificar_caso_acesso"
    description: str = _load_instructions(__file__)
    args_schema: type[BaseModel] = _Input

    _use_case: VerificarCasoAcesso

    def __init__(self, use_case: VerificarCasoAcesso) -> None:
        super().__init__()
        self._use_case = use_case

    def _run(self, email: str) -> str:  # pragma: no cover
        raise NotImplementedError("Use async")

    async def _arun(self, email: str) -> str:
        cfg = get_config()["configurable"]
        account_id: str = cfg["account_id"]

        for pre in PRECONDITIONS:
            if not pre.passed:
                return pre.block_message

        result = await self._use_case.execute(email=email, account_id=account_id)
        if not result["tem_caso"]:
            return "Nenhum caso de acesso encontrado para este aluno."
        return f"Caso encontrado. Status: {result['status']}. ID: {result['caso_id']}."
