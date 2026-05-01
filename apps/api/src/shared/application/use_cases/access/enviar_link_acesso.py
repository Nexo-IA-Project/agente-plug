from __future__ import annotations

from typing import Any

import structlog

from nexoia.domain.ports.cademi_port import CademiPort
from nexoia.domain.ports.chatnexo import ChatNexoPort

log = structlog.get_logger(__name__)

ACCESS_FREE_TEXT = "Tudo certo! Aqui tá seu acesso, {name} — é só clicar que já entra direto: {link}"
ACCESS_RESEND_TEMPLATE = "access_reminder_d1"


class EnviarLinkAcesso:
    def __init__(self, repo: Any, cademi: CademiPort, chatnexo: ChatNexoPort) -> None:
        self._repo = repo
        self._cademi = cademi
        self._chatnexo = chatnexo

    async def execute(
        self,
        account_id: str,
        phone: str,
        student_id: str,
        student_name: str,
        within_24h_window: bool = True,
        conversation_id: str | None = None,
    ) -> str:
        case = await self._repo.find_by_phone(account_id=account_id, phone=phone)
        if case is None:
            return "ERRO: Caso de acesso não encontrado ao tentar enviar link."

        purchase_id = case.purchase_id or ""
        link = await self._cademi.get_access_link(
            student_id=student_id, product_id=purchase_id
        )

        first_name = (student_name or "").split()[0] if student_name else ""

        if within_24h_window:
            text = ACCESS_FREE_TEXT.format(name=first_name, link=link)
            await self._chatnexo.send_message(
                account_id=account_id,
                conversation_id=conversation_id,
                text=text,
            )
        else:
            await self._chatnexo.send_template(
                account_id=account_id,
                conversation_id=conversation_id,
                template_name=ACCESS_RESEND_TEMPLATE,
                variables={"1": student_name or "", "2": case.product_name or "", "3": link},
            )

        log.info("access_link_sent", account_id=account_id, within_24h=within_24h_window)
        return f"LINK_ENVIADO: {link}"
