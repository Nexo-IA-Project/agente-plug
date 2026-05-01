from __future__ import annotations

from typing import Any, Type

from langchain_core.tools import BaseTool
from langgraph.config import get_config
from pydantic import BaseModel, ConfigDict

from shared.application.use_cases.refund.iniciar_retencao import IniciarRetencao
from shared.application.use_cases.refund.processar_reembolso import ProcessarReembolso
from shared.application.use_cases.refund.verificar_elegibilidade import VerificarElegibilidadeReembolso
from shared.domain.ports.hubla_port import HublaPort
from shared.domain.ports.legal_history_port import LegalHistoryPort
from shared.domain.ports.refund_mutex import RefundMutexPort


class VerificarElegibilidadeInput(BaseModel):
    motivo: str
    email: str
    cpf: str


class VerificarElegibilidadeReembolsoTool(BaseTool):
    name: str = "verificar_elegibilidade_reembolso"
    description: str = (
        "Verifica elegibilidade do aluno para reembolso (CDC 7 dias).\n"
        "Use quando: aluno solicita reembolso e forneceu motivo + email + CPF.\n"
        "Não use quando: dados incompletos — colete-os conversacionalmente antes.\n"
        "Retorna: ELEGIVEL / INELEGIVEL com data / COMPRA_DUPLICADA."
    )
    args_schema: Type[BaseModel] = VerificarElegibilidadeInput

    verificar_uc: Any

    model_config = ConfigDict(arbitrary_types_allowed=True)

    async def _arun(self, motivo: str, email: str, cpf: str) -> str:
        cfg = get_config()["configurable"]
        return await self.verificar_uc.execute(
            cfg["account_id"], cfg["phone"], cfg.get("conversation_id", ""), motivo, email, cpf
        )

    def _run(self, **_: object) -> str:
        raise NotImplementedError


class EmptyInput(BaseModel):
    pass


class OfereceRetencaoTool(BaseTool):
    name: str = "oferecer_retencao"
    description: str = (
        "Oferece retenção N1 ou N2 ao aluno elegível para reembolso.\n"
        "Use quando: aluno é elegível (dentro do prazo, não duplicada) e ainda não recusou N2.\n"
        "Não use quando: compra duplicada, N2 já recusado, ou aluno fora do prazo.\n"
        "Retorna: texto da oferta N1/N2 ou RETENCAO_ESGOTADA."
    )
    args_schema: Type[BaseModel] = EmptyInput

    reter_uc: Any

    model_config = ConfigDict(arbitrary_types_allowed=True)

    async def _arun(self) -> str:
        cfg = get_config()["configurable"]
        return await self.reter_uc.execute(cfg["account_id"], cfg["phone"])

    def _run(self, **_: object) -> str:
        raise NotImplementedError


class ProcessarReembolsoTool(BaseTool):
    name: str = "processar_reembolso"
    description: str = (
        "Processa o reembolso após dupla recusa de retenção ou compra duplicada.\n"
        "Use quando: aluno recusou N1 e N2, OU compra duplicada confirmada.\n"
        "Não use quando: N2 ainda não foi oferecido — invariante bloqueará e retornará erro.\n"
        "Retorna: mensagem padrão de processamento (PRD 7.3)."
    )
    args_schema: Type[BaseModel] = EmptyInput

    processar_uc: Any

    model_config = ConfigDict(arbitrary_types_allowed=True)

    async def _arun(self) -> str:
        cfg = get_config()["configurable"]
        return await self.processar_uc.execute(cfg["account_id"], cfg["phone"])

    def _run(self, **_: object) -> str:
        raise NotImplementedError


def make_refund_skills(
    refund_repo: object,
    hubla: HublaPort,
    legal_history: LegalHistoryPort,
    refund_mutex: RefundMutexPort,
) -> list[BaseTool]:
    return [
        VerificarElegibilidadeReembolsoTool(
            verificar_uc=VerificarElegibilidadeReembolso(refund_repo, hubla, legal_history),
        ),
        OfereceRetencaoTool(
            reter_uc=IniciarRetencao(refund_repo),
        ),
        ProcessarReembolsoTool(
            processar_uc=ProcessarReembolso(refund_repo, hubla, refund_mutex),
        ),
    ]
