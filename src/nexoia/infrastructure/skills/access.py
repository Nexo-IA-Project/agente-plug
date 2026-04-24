from __future__ import annotations

from langchain_core.tools import BaseTool, tool
from langgraph.config import get_config

from nexoia.application.use_cases.access.buscar_aluno_cademi import BuscarAlunoCademi
from nexoia.application.use_cases.access.enviar_link_acesso import EnviarLinkAcesso
from nexoia.application.use_cases.access.verificar_caso import VerificarCasoAcesso
from nexoia.domain.ports.cademi_port import CademiPort
from nexoia.domain.ports.chatnexo import ChatNexoPort


def make_access_skills(
    access_repo: object,
    cademi: CademiPort,
    chatnexo: ChatNexoPort,
) -> list[BaseTool]:
    verificar_uc = VerificarCasoAcesso(repo=access_repo, chatnexo=chatnexo)
    buscar_uc = BuscarAlunoCademi(repo=access_repo, cademi=cademi)
    enviar_uc = EnviarLinkAcesso(repo=access_repo, cademi=cademi, chatnexo=chatnexo)

    @tool
    async def verificar_caso_acesso(last_message: str = "") -> str:
        """
        Verifica se existe caso de acesso aberto para o aluno.
        Use quando: aluno relata problema de acesso ao produto.
        Retorna: CASO_ENCONTRADO com detalhes, ou ESCALADO se não houver caso.
        Não use quando: acesso já foi verificado nesta conversa.
        """
        cfg = get_config()["configurable"]
        return await verificar_uc.execute(
            account_id=cfg["account_id"],
            phone=cfg["phone"],
            last_message=last_message,
        )

    @tool
    async def buscar_aluno_cademi(
        email: str | None = None,
        cpf: str | None = None,
    ) -> str:
        """
        Busca aluno na Cademi por email ou CPF (cascata: email → CPF → nome+telefone).
        Use quando: precisa localizar cadastro para enviar acesso. Tente email primeiro, CPF se falhar.
        Retorna: ENCONTRADO com nome e student_id, SOLICITAR_CPF, ou ESCALADO.
        Não use quando: aluno já foi localizado (student_id disponível).
        """
        cfg = get_config()["configurable"]
        return await buscar_uc.execute(
            account_id=cfg["account_id"],
            phone=cfg["phone"],
            email=email,
            cpf=cpf,
        )

    @tool
    async def enviar_link_acesso(
        student_id: str,
        student_name: str,
        within_24h_window: bool = True,
    ) -> str:
        """
        Envia link de acesso ao aluno após localização na Cademi.
        Use quando: aluno foi localizado (ENCONTRADO) e está sem acesso ao produto.
        Não use quando: aluno ainda não foi localizado — use buscar_aluno_cademi antes.
        Retorna: LINK_ENVIADO com a URL, ou ERRO.
        """
        cfg = get_config()["configurable"]
        return await enviar_uc.execute(
            account_id=cfg["account_id"],
            phone=cfg["phone"],
            student_id=student_id,
            student_name=student_name,
            within_24h_window=within_24h_window,
            conversation_id=cfg.get("conversation_id"),
        )

    return [verificar_caso_acesso, buscar_aluno_cademi, enviar_link_acesso]
