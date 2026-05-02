from __future__ import annotations

import asyncio
import contextlib
from typing import Any

import structlog
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.config import RunnableConfig

from agent.guards import GuardService
from agent.prompt import build_system_prompt
from agent.state import AgentState
from shared.domain.policies.communication_rules import CommunicationRules

log = structlog.get_logger(__name__)

_CANCEL_WORDS = ("cancela", "para", "esquece", "desiste")
_FALLBACK_MESSAGE = (
    "Desculpe, não consegui processar sua solicitação. Um humano vai te ajudar em breve."
)
_communication_rules = CommunicationRules()


def _is_cancel(content: str) -> bool:
    return any(w in content.lower() for w in _CANCEL_WORDS)


def _roteador(state: AgentState) -> str:
    """Routes after raciocinar: execute tool if LLM made a tool call, else END."""
    from langgraph.graph import END

    last = state["messages"][-1]
    return "executar" if getattr(last, "tool_calls", None) else END


def make_raciocinar_node(
    guard_service: GuardService,
    long_term_repo: Any,
    llm: Any,
):
    async def raciocinar(state: AgentState, config: RunnableConfig) -> dict:
        cfg = config["configurable"]
        ultima = state["messages"][-1]

        # Fila inteligente — aguarda skill em andamento
        if state.get("skill_em_andamento"):
            if _is_cancel(ultima.content):
                return {
                    "skill_em_andamento": None,
                    "messages": [AIMessage("Ok, cancelei. Como posso ajudar?")],
                }
            return {
                "mensagens_pendentes": [*state.get("mensagens_pendentes", []), ultima.content],
                "messages": [AIMessage("Já estou resolvendo isso, um momentinho!")],
            }

        # 1. Guards pré-LLM
        guard_result = guard_service.check(ultima.content, state)
        if guard_result.blocked:
            if guard_result.forced_instruction:
                msgs = [SystemMessage(guard_result.forced_instruction), *state["messages"]]
                response = await llm.ainvoke(msgs, config)
                update: dict = {"messages": [response]}
                if getattr(response, "tool_calls", None):
                    update["skill_em_andamento"] = response.tool_calls[0]["name"]
                return update
            return {"messages": [AIMessage(guard_result.response or _FALLBACK_MESSAGE)]}

        # 2. Long-term facts → system prompt dinâmico
        facts = await long_term_repo.load(cfg["account_id"], cfg["phone"])
        system_prompt = build_system_prompt(long_term_facts=facts)

        # 3. LLM
        msgs = [SystemMessage(system_prompt), *state["messages"]]
        response = await llm.ainvoke(msgs, config)

        # 4. CommunicationRules — valida resposta (só para texto livre, não tool_call)
        if not getattr(response, "tool_calls", None):
            for _ in range(2):
                validated = _communication_rules.validate(response.content)
                if validated.ok:
                    break
                correction_msgs = [*msgs, SystemMessage(validated.correction_hint)]
                response = await llm.ainvoke(correction_msgs, config)
            else:
                validated = _communication_rules.validate(response.content)
                if not validated.ok:
                    response = AIMessage(_FALLBACK_MESSAGE)

        update: dict = {"messages": [response]}
        if getattr(response, "tool_calls", None):
            update["skill_em_andamento"] = response.tool_calls[0]["name"]
        return update

    return raciocinar


def make_pos_execucao_node(capability_repo: Any, memory_extractor: Any):
    async def pos_execucao(state: AgentState, config: RunnableConfig) -> dict:
        cfg = config["configurable"]
        skill_name = state.get("skill_em_andamento")
        update: dict = {"skill_em_andamento": None, "mensagens_pendentes": []}

        # Background tasks — fire-and-forget; stored only to satisfy RUF006
        _bg_tasks: list[asyncio.Task] = []

        # Registra analytics em background
        if skill_name and capability_repo:
            with contextlib.suppress(RuntimeError):
                _bg_tasks.append(
                    asyncio.create_task(
                        capability_repo.record(
                            conversation_id=cfg["conversation_id"],
                            skill_name=skill_name,
                        )
                    )
                )

        # Extrai long_term_facts em background
        if memory_extractor:
            with contextlib.suppress(RuntimeError):
                _bg_tasks.append(
                    asyncio.create_task(
                        memory_extractor.extract_and_save(
                            account_id=cfg["account_id"],
                            phone=cfg["phone"],
                            messages=state["messages"],
                        )
                    )
                )

        # Reinjeta mensagens pendentes para o próximo turno de raciocinar
        pending = state.get("mensagens_pendentes") or []
        if pending:
            joined = " | ".join(pending)
            update["messages"] = [HumanMessage(f"[mensagens_pendentes]: {joined}")]

        return update

    return pos_execucao
