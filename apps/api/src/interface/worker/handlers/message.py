from __future__ import annotations

from typing import Any

import structlog
from langchain_core.messages import AIMessage, HumanMessage

from shared.adapters.redis.lead_lock import LeadLock, LeadLockError
from shared.application.lifecycle_handler import LifecycleHandler
from shared.application.message_dispatcher import MessageDispatcher

log = structlog.get_logger(__name__)


def _get_agent() -> Any:
    """Monta e retorna o grafo compilado. Singleton por processo."""
    # TODO: injetar deps reais de infraestrutura (session factory, redis, etc.)
    # Placeholder — substituir por DI container quando disponível
    raise NotImplementedError("_get_agent: configure DI container em main.py e injete via closure")


def _get_dispatcher() -> MessageDispatcher:
    raise NotImplementedError("_get_dispatcher: configure em main.py")


def _get_lifecycle() -> LifecycleHandler:
    raise NotImplementedError("_get_lifecycle: configure em main.py")


def _get_scheduler() -> Any:
    raise NotImplementedError("_get_scheduler: configure em main.py")


async def handle_message(payload: dict[str, Any], *, lead_lock: LeadLock | None = None) -> None:
    account_id: str = payload["account_id"]
    phone: str = payload["phone"]
    conversation_id: str = payload["conversation_id"]
    text: str = payload["text"]

    log.info(
        "message_job_started",
        account_id=account_id,
        phone=phone,
        conversation_id=conversation_id,
    )

    if lead_lock is not None:
        try:
            async with lead_lock.acquire(account_id=account_id, phone=phone):
                await _process_message(
                    account_id=account_id,
                    phone=phone,
                    conversation_id=conversation_id,
                    text=text,
                )
        except LeadLockError:
            log.warning(
                "message_job_lead_locked",
                account_id=account_id,
                phone=phone,
                conversation_id=conversation_id,
            )
            raise
    else:
        await _process_message(
            account_id=account_id,
            phone=phone,
            conversation_id=conversation_id,
            text=text,
        )

    log.info("message_job_done", account_id=account_id, conversation_id=conversation_id)


async def _process_message(
    *,
    account_id: str,
    phone: str,
    conversation_id: str,
    text: str,
) -> None:
    agent = _get_agent()
    dispatcher = _get_dispatcher()
    lifecycle = _get_lifecycle()
    scheduler = _get_scheduler()

    # Cancela jobs de idle pendentes (nova mensagem = aluno voltou)
    await scheduler.cancel_pending_idle_jobs(account_id=account_id, phone=phone)

    config = {
        "configurable": {
            "thread_id": f"{account_id}:{phone}",
            "account_id": account_id,
            "phone": phone,
            "conversation_id": conversation_id,
        }
    }

    result = await agent.ainvoke(
        {"messages": [HumanMessage(text)]},
        config=config,
    )

    # Extrai última AIMessage sem tool_call — é a resposta ao aluno
    last_ai = next(
        (
            m
            for m in reversed(result.get("messages", []))
            if isinstance(m, AIMessage) and not getattr(m, "tool_calls", None)
        ),
        None,
    )

    if last_ai and last_ai.content:
        await dispatcher.send(
            account_id=account_id,
            conversation_id=conversation_id,
            content=last_ai.content,
        )

    # Agenda idle check
    await lifecycle.schedule_idle_ping(
        account_id=account_id,
        phone=phone,
        conversation_id=conversation_id,
    )
