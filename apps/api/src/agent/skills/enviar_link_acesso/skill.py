# apps/api/src/agent/skills/enviar_link_acesso/skill.py
from __future__ import annotations

from langchain_core.tools import BaseTool
from langgraph.config import get_config
from pydantic import BaseModel, ConfigDict

from agent.skills._utils import _load_instructions
from agent.skills.enviar_link_acesso.preconditions import PRECONDITIONS
from agent.skills.enviar_link_acesso.use_case import EnviarLinkAcesso


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str
    phone: str


class EnviarLinkAcessoTool(BaseTool):
    name: str = "enviar_link_acesso"
    description: str = _load_instructions(__file__)
    args_schema: type[BaseModel] = _Input

    _use_case: EnviarLinkAcesso

    def __init__(self, use_case: EnviarLinkAcesso) -> None:
        super().__init__()
        self._use_case = use_case

    def _run(self, email: str, phone: str) -> str:  # pragma: no cover
        raise NotImplementedError("Use async")

    async def _arun(self, email: str, phone: str) -> str:
        cfg = get_config()["configurable"]
        account_id: str = cfg["account_id"]

        for pre in PRECONDITIONS:
            if not pre.passed:
                return pre.block_message

        result = await self._use_case.execute(email=email, phone=phone, account_id=account_id)
        if not result["enviado"]:
            return result["mensagem"]
        return f"Link de acesso enviado com sucesso para {phone}."
