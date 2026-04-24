from __future__ import annotations

from langchain_core.tools import BaseTool, tool
from langgraph.config import get_config

from nexoia.application.use_cases.refund.iniciar_retencao import IniciarRetencao
from nexoia.application.use_cases.refund.processar_reembolso import ProcessarReembolso
from nexoia.application.use_cases.refund.verificar_elegibilidade import VerificarElegibilidadeReembolso
from nexoia.domain.ports.hubla_port import HublaPort
from nexoia.domain.ports.legal_history_port import LegalHistoryPort
from nexoia.domain.ports.refund_mutex import RefundMutexPort


def make_refund_skills(
    refund_repo: object,
    hubla: HublaPort,
    legal_history: LegalHistoryPort,
    refund_mutex: RefundMutexPort,
) -> list[BaseTool]:
    verificar_uc = VerificarElegibilidadeReembolso(refund_repo, hubla, legal_history)
    reter_uc     = IniciarRetencao(refund_repo)
    processar_uc = ProcessarReembolso(refund_repo, hubla, refund_mutex)

    @tool
    async def verificar_elegibilidade_reembolso(motivo: str, email: str, cpf: str) -> str:
        """
        Verifica elegibilidade do aluno para reembolso (CDC 7 dias).
        Use quando: aluno solicita reembolso e forneceu motivo + email + CPF.
        Não use quando: dados incompletos — colete-os conversacionalmente antes.
        Retorna: ELEGIVEL / INELEGIVEL com data / COMPRA_DUPLICADA.
        """
        cfg = get_config()["configurable"]
        return await verificar_uc.execute(
            cfg["account_id"], cfg["phone"], cfg.get("conversation_id", ""), motivo, email, cpf
        )

    @tool
    async def oferecer_retencao() -> str:
        """
        Oferece retenção N1 ou N2 ao aluno elegível para reembolso.
        Use quando: aluno é elegível (dentro do prazo, não duplicada) e ainda não recusou N2.
        Não use quando: compra duplicada, N2 já recusado, ou aluno fora do prazo.
        Retorna: texto da oferta N1/N2 ou RETENCAO_ESGOTADA.
        """
        cfg = get_config()["configurable"]
        return await reter_uc.execute(cfg["account_id"], cfg["phone"])

    @tool
    async def processar_reembolso() -> str:
        """
        Processa o reembolso após dupla recusa de retenção ou compra duplicada.
        Use quando: aluno recusou N1 e N2, OU compra duplicada confirmada.
        Não use quando: N2 ainda não foi oferecido — invariante bloqueará e retornará erro.
        Retorna: mensagem padrão de processamento (PRD 7.3).
        """
        cfg = get_config()["configurable"]
        return await processar_uc.execute(cfg["account_id"], cfg["phone"])

    return [verificar_elegibilidade_reembolso, oferecer_retencao, processar_reembolso]
