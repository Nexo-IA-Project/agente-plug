# apps/api/src/agent/skills/enviar_link_acesso/use_case.py
from __future__ import annotations

from shared.domain.ports.cademi_port import CademiPort
from shared.domain.ports.chatnexo import ChatNexoPort


class EnviarLinkAcesso:
    def __init__(self, cademi: CademiPort, chatnexo: ChatNexoPort) -> None:
        self._cademi = cademi
        self._chatnexo = chatnexo

    async def execute(self, email: str, phone: str, account_id: str) -> dict:
        link = await self._cademi.gerar_link_acesso(email=email, account_id=account_id)
        if link is None:
            return {"enviado": False, "mensagem": "Não foi possível gerar o link de acesso."}
        await self._chatnexo.enviar_mensagem(
            phone=phone,
            account_id=account_id,
            mensagem=f"Aqui está seu link de acesso: {link}",
        )
        return {"enviado": True, "link": link}
