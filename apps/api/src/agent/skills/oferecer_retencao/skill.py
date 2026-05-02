# apps/api/src/agent/skills/oferecer_retencao/skill.py
from __future__ import annotations

from langchain_core.tools import BaseTool
from langgraph.config import get_config
from pydantic import BaseModel, ConfigDict

from agent.skills._utils import _load_instructions
from agent.skills.oferecer_retencao.preconditions import PRECONDITIONS
from agent.skills.oferecer_retencao.use_case import OfereceRetencao


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str
    produto_id: str


class OfereceRetencaoTool(BaseTool):
    name: str = "oferecer_retencao"
    description: str = _load_instructions(__file__)
    args_schema: type[BaseModel] = _Input

    _use_case: OfereceRetencao

    def __init__(self, use_case: OfereceRetencao) -> None:
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
        if not result["tem_oferta"]:
            return "Nenhuma oferta de retenção disponível para este perfil."
        return (
            f"Oferta de retenção disponível: {result['descricao']}. "
            f"Tipo: {result['tipo']}. "
            f"Desconto: R$ {result['valor_desconto']:.2f}."
        )
