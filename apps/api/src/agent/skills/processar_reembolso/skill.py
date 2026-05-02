# apps/api/src/agent/skills/processar_reembolso/skill.py
from __future__ import annotations

from langchain_core.tools import BaseTool
from langgraph.config import get_config
from pydantic import BaseModel, ConfigDict

from agent.skills._utils import _load_instructions
from agent.skills.processar_reembolso.preconditions import PRECONDITIONS
from agent.skills.processar_reembolso.use_case import ProcessarReembolso


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str
    produto_id: str


class ProcessarReembolsoTool(BaseTool):
    name: str = "processar_reembolso"
    description: str = _load_instructions(__file__)
    args_schema: type[BaseModel] = _Input

    _use_case: ProcessarReembolso

    def __init__(self, use_case: ProcessarReembolso) -> None:
        super().__init__()
        self._use_case = use_case

    def _run(self, email: str, produto_id: str) -> str:  # pragma: no cover
        raise NotImplementedError("Use async")

    async def _arun(self, email: str, produto_id: str) -> str:
        cfg = get_config()["configurable"]
        account_id: str = cfg["account_id"]

        for pre in PRECONDITIONS:
            if not pre.passed:
                return pre.block_message

        result = await self._use_case.execute(
            email=email, produto_id=produto_id, account_id=account_id
        )
        if not result["processado"]:
            return f"Reembolso não processado: {result['motivo']}"
        return (
            f"Reembolso processado com sucesso. "
            f"Protocolo: {result['protocolo']}. "
            f"Valor: R$ {result['valor']:.2f}. "
            f"Prazo de estorno: {result['prazo_estorno']}."
        )
