from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import structlog

from nexoia.domain.ports.chatnexo import ChatNexoPort

log = structlog.get_logger(__name__)

_PING_VARIATIONS = [
    "Olá, {nome}, você está por aí ainda?",
    "Ei {nome}, ainda tá comigo?",
    "{nome}, tudo certo? Continuo aqui se quiser seguir.",
]
_CLOSE_VARIATIONS = [
    "Como não vi mais sua resposta, vou encerrar por aqui. Qualquer coisa me chama!",
    "Sem resposta por aqui, então vou encerrando. Quando quiser retomar é só mandar mensagem.",
    "Vou finalizar por enquanto, {nome}. Quando quiser retomar, é só me chamar.",
]
_SKIP_STATUSES = {"HANDED_OFF", "CLOSED_BY_TIMEOUT"}


class LifecycleHandler:
    def __init__(
        self,
        conv_repo: Any,
        contact_repo: Any,
        chatnexo: ChatNexoPort,
        scheduler: Any,
    ) -> None:
        self._conv_repo = conv_repo
        self._contact_repo = contact_repo
        self._chatnexo = chatnexo
        self._scheduler = scheduler

    async def send_ping(self, account_id: str, phone: str, conversation_id: str) -> None:
        conv = await self._conv_repo.find_active(account_id, conversation_id)
        if conv is None or str(conv.status) in _SKIP_STATUSES:
            return
        if conv.window_expires_at <= datetime.now(UTC):
            await self._conv_repo.update_status(conv.id, "CLOSED_BY_TIMEOUT")
            return

        contact = await self._contact_repo.find_by_phone(account_id, phone)
        nome = (contact.name or "").split()[0] if contact else ""
        idx = hash(f"{conversation_id}:ping") % len(_PING_VARIATIONS)
        text = _PING_VARIATIONS[idx].format(nome=nome)

        await self._chatnexo.send_message(
            account_id=account_id, conversation_id=conversation_id, text=text
        )
        await self._conv_repo.update_status(conv.id, "IDLE_PINGED")
        await self._scheduler.create_job(
            job_type="IDLE_CLOSE",
            account_id=account_id,
            conversation_id=conversation_id,
            run_at=datetime.now(UTC) + timedelta(minutes=20),
        )
        log.info("idle_ping_sent", account_id=account_id, conversation_id=conversation_id)

    async def send_close(self, account_id: str, phone: str, conversation_id: str) -> None:
        conv = await self._conv_repo.find_active(account_id, conversation_id)
        if conv is None or str(conv.status) != "IDLE_PINGED":
            return

        contact = await self._contact_repo.find_by_phone(account_id, phone)
        nome = (contact.name or "").split()[0] if contact else ""
        idx = hash(f"{conversation_id}:close") % len(_CLOSE_VARIATIONS)
        text = _CLOSE_VARIATIONS[idx].format(nome=nome)

        await self._chatnexo.send_message(
            account_id=account_id, conversation_id=conversation_id, text=text
        )
        await self._conv_repo.update_status(conv.id, "CLOSED_BY_TIMEOUT")
        log.info("idle_close_sent", account_id=account_id, conversation_id=conversation_id)

    async def schedule_idle_ping(
        self, account_id: str, phone: str, conversation_id: str
    ) -> None:
        await self._scheduler.create_job(
            job_type="IDLE_PING",
            account_id=account_id,
            conversation_id=conversation_id,
            run_at=datetime.now(UTC) + timedelta(minutes=30),
        )
