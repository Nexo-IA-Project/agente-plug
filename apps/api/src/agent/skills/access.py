from __future__ import annotations

from typing import Any, Type

from langchain_core.tools import BaseTool
from langgraph.config import get_config
from pydantic import BaseModel, ConfigDict

from shared.application.use_cases.access.buscar_aluno_cademi import BuscarAlunoCademi
from shared.application.use_cases.access.enviar_link_acesso import EnviarLinkAcesso
from shared.application.use_cases.access.verificar_caso import VerificarCasoAcesso
from shared.domain.ports.cademi_port import CademiPort
from shared.domain.ports.chatnexo import ChatNexoPort


class VerificarCasoAcessoInput(BaseModel):
    last_message: str = ""


class VerificarCasoAcessoTool(BaseTool):
    name: str = "verificar_caso_acesso"
    description: str = (
        "Verifica se existe caso de acesso aberto para o aluno.\n"
        "Use quando: aluno relata problema de acesso ao produto.\n"
        "Retorna: CASO_ENCONTRADO com detalhes, ou ESCALADO se não houver caso.\n"
        "Não use quando: acesso já foi verificado nesta conversa."
    )
    args_schema: Type[BaseModel] = VerificarCasoAcessoInput

    verificar_uc: Any

    model_config = ConfigDict(arbitrary_types_allowed=True)

    async def _arun(self, last_message: str = "") -> str:
        cfg = get_config()["configurable"]
        return await self.verificar_uc.execute(
            account_id=cfg["account_id"],
            phone=cfg["phone"],
            last_message=last_message,
        )

    def _run(self, **_: object) -> str:
        raise NotImplementedError


class BuscarAlunoCademiInput(BaseModel):
    email: str | None = None
    cpf: str | None = None


class BuscarAlunoCademiTool(BaseTool):
    name: str = "buscar_aluno_cademi"
    description: str = (
        "Busca aluno na Cademi por email ou CPF (cascata: email → CPF → nome+telefone).\n"
        "Use quando: precisa localizar cadastro para enviar acesso. Tente email primeiro, CPF se falhar.\n"
        "Retorna: ENCONTRADO com nome e student_id, SOLICITAR_CPF, ou ESCALADO.\n"
        "Não use quando: aluno já foi localizado (student_id disponível)."
    )
    args_schema: Type[BaseModel] = BuscarAlunoCademiInput

    buscar_uc: Any

    model_config = ConfigDict(arbitrary_types_allowed=True)

    async def _arun(self, email: str | None = None, cpf: str | None = None) -> str:
        cfg = get_config()["configurable"]
        return await self.buscar_uc.execute(
            account_id=cfg["account_id"],
            phone=cfg["phone"],
            email=email,
            cpf=cpf,
        )

    def _run(self, **_: object) -> str:
        raise NotImplementedError


class EnviarLinkAcessoInput(BaseModel):
    student_id: str
    student_name: str
    within_24h_window: bool = True


class EnviarLinkAcessoTool(BaseTool):
    name: str = "enviar_link_acesso"
    description: str = (
        "Envia link de acesso ao aluno após localização na Cademi.\n"
        "Use quando: aluno foi localizado (ENCONTRADO) e está sem acesso ao produto.\n"
        "Não use quando: aluno ainda não foi localizado — use buscar_aluno_cademi antes.\n"
        "Retorna: LINK_ENVIADO com a URL, ou ERRO."
    )
    args_schema: Type[BaseModel] = EnviarLinkAcessoInput

    enviar_uc: Any

    model_config = ConfigDict(arbitrary_types_allowed=True)

    async def _arun(
        self, student_id: str, student_name: str, within_24h_window: bool = True
    ) -> str:
        cfg = get_config()["configurable"]
        return await self.enviar_uc.execute(
            account_id=cfg["account_id"],
            phone=cfg["phone"],
            student_id=student_id,
            student_name=student_name,
            within_24h_window=within_24h_window,
            conversation_id=cfg.get("conversation_id"),
        )

    def _run(self, **_: object) -> str:
        raise NotImplementedError


def make_access_skills(
    access_repo: object,
    cademi: CademiPort,
    chatnexo: ChatNexoPort,
) -> list[BaseTool]:
    return [
        VerificarCasoAcessoTool(
            verificar_uc=VerificarCasoAcesso(repo=access_repo, chatnexo=chatnexo),
        ),
        BuscarAlunoCademiTool(
            buscar_uc=BuscarAlunoCademi(repo=access_repo, cademi=cademi),
        ),
        EnviarLinkAcessoTool(
            enviar_uc=EnviarLinkAcesso(repo=access_repo, cademi=cademi, chatnexo=chatnexo),
        ),
    ]
