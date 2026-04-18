from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import timedelta
from typing import Protocol
from uuid import UUID

from nexoia.domain.entities.conversation import Conversation, ConversationStatus, IdleState
from nexoia.domain.entities.scheduled_job import JobType


_PING_VARIATIONS = [
    "Olá, {name}, você está por aí ainda?",
    "Ei {name}, ainda tá comigo?",
    "{name}, tudo certo? Continuo aqui se quiser seguir.",
]

_CLOSE_VARIATIONS = [
    "Como não vi mais sua resposta, vou encerrar a conversa por aqui. Se quiser retomar, é só me chamar. 🙂",
    "Sem resposta por aqui, então vou encerrando. Qualquer coisa me avisa que a gente continua.",
    "Vou finalizar por aqui por enquanto, {name}. Quando quiser retomar, é só mandar mensagem.",
]


class ChatNexoSender(Protocol):
    async def send_message(
        self, *, account_id: UUID, conversation_id: int, text: str
    ) -> None: ...


class ScheduledRepoProto(Protocol):
    async def schedule(self, **kwargs) -> object: ...
    async def cancel_by_conversation(self, **kwargs) -> int: ...


class ConvRepoProto(Protocol):
    async def update_status(self, **kwargs) -> None: ...


class ClockProto(Protocol):
    def now(self): ...


@dataclass
class ConversationLifecycleManager:
    scheduled_repo: ScheduledRepoProto
    conv_repo: ConvRepoProto
    chatnexo: ChatNexoSender
    clock: ClockProto
    ping_minutes: int = 30
    close_minutes: int = 20

    def _pick_variation(self, conv_id: UUID, stage: str, *, name: str) -> str:
        pool = _PING_VARIATIONS if stage == "ping" else _CLOSE_VARIATIONS
        digest = hashlib.sha256(f"{conv_id}:{stage}".encode()).digest()
        idx = digest[0] % len(pool)
        return pool[idx].replace("{name}", name or "")

    async def on_agent_outbound(
        self, *, conversation: Conversation, correlation_id: str | None = None
    ) -> None:
        """Called after the agent sends a message — schedule idle ping in +N minutes."""
        await self.scheduled_repo.cancel_by_conversation(
            account_id=conversation.account_id,
            conversation_id=conversation.id,
            job_types=[JobType.IDLE_PING, JobType.IDLE_CLOSE],
        )
        await self.scheduled_repo.schedule(
            account_id=conversation.account_id,
            conversation_id=conversation.id,
            job_type=JobType.IDLE_PING,
            payload={},
            run_at=self.clock.now() + timedelta(minutes=self.ping_minutes),
            correlation_id=correlation_id,
        )

    async def on_student_message(self, *, conversation: Conversation) -> None:
        """Student replied — cancel any pending idle jobs."""
        await self.scheduled_repo.cancel_by_conversation(
            account_id=conversation.account_id,
            conversation_id=conversation.id,
            job_types=[JobType.IDLE_PING, JobType.IDLE_CLOSE],
        )

    async def fire_ping(
        self, *, conversation: Conversation, contact_name: str, correlation_id: str | None = None
    ) -> None:
        if conversation.status == ConversationStatus.HANDED_OFF:
            return
        if not conversation.is_inside_meta_window(now=self.clock.now()):
            conversation.mark_closed_by_timeout()
            return

        text = self._pick_variation(conversation.id, "ping", name=contact_name)
        await self.chatnexo.send_message(
            account_id=conversation.account_id,
            conversation_id=conversation.chatnexo_conversation_id,
            text=text,
        )
        conversation.idle_state = IdleState.PING_SENT
        await self.scheduled_repo.schedule(
            account_id=conversation.account_id,
            conversation_id=conversation.id,
            job_type=JobType.IDLE_CLOSE,
            payload={},
            run_at=self.clock.now() + timedelta(minutes=self.close_minutes),
            correlation_id=correlation_id,
        )

    async def fire_close(
        self, *, conversation: Conversation, contact_name: str, correlation_id: str | None = None
    ) -> None:
        if conversation.status == ConversationStatus.HANDED_OFF:
            return
        if not conversation.is_inside_meta_window(now=self.clock.now()):
            conversation.mark_closed_by_timeout()
            return
        text = self._pick_variation(conversation.id, "close", name=contact_name)
        await self.chatnexo.send_message(
            account_id=conversation.account_id,
            conversation_id=conversation.chatnexo_conversation_id,
            text=text,
        )
        conversation.mark_closed_by_timeout()
