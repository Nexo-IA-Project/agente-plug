"""OpenAI function calling agent loop."""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, cast

import structlog
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam, ChatCompletionToolParam
from openai.types.chat.chat_completion import Choice
from openai.types.chat.chat_completion_message_function_tool_call import (
    ChatCompletionMessageFunctionToolCall,
)
from sqlalchemy.ext.asyncio import AsyncSession

from agent.context import AgentContext
from agent.guards import GuardService
from agent.history import ConversationHistory
from agent.prompt import build_system_prompt
from agent.tool_registry import ToolRegistry
from shared.adapters.observability.metrics import (
    AGENT_ITERATIONS,
    AGENT_RUN_DURATION,
    AGENT_TOOL_CALLS,
)

log = structlog.get_logger(__name__)

_MAX_ITERATIONS = 10
_FALLBACK = "Desculpe, não consegui processar sua solicitação. Um humano vai te ajudar em breve."


async def run_agent(
    *,
    ctx: AgentContext,
    user_message: str,
    registry: ToolRegistry,
    session: AsyncSession,
    client: AsyncOpenAI,
    long_term_facts: list[str] | None = None,
    guard_service: GuardService | None = None,
    model: str = "gpt-4o",
    memory_limit: int | None = None,
) -> str:
    """Run the agent loop for one user turn. Returns the assistant's final reply.

    ``memory_limit`` define quantas mensagens recentes do histórico são carregadas
    como contexto. ``None`` carrega tudo (compat).
    """
    t0 = time.monotonic()
    outcome = "success"
    try:
        reply = await _run(
            ctx=ctx,
            user_message=user_message,
            registry=registry,
            session=session,
            client=client,
            long_term_facts=long_term_facts or [],
            guard_service=guard_service,
            model=model,
            memory_limit=memory_limit,
        )
    except Exception:
        outcome = "error"
        raise
    finally:
        AGENT_RUN_DURATION.labels(outcome=outcome).observe(time.monotonic() - t0)
    return reply


async def _run(
    *,
    ctx: AgentContext,
    user_message: str,
    registry: ToolRegistry,
    session: AsyncSession,
    client: AsyncOpenAI,
    long_term_facts: list[str],
    guard_service: GuardService | None,
    model: str,
    memory_limit: int | None = None,
) -> str:
    history = ConversationHistory(session=session)
    # Carrega o histórico completo para persistência; usa apenas as últimas
    # ``memory_limit`` mensagens como contexto para o LLM. ``memory_limit``
    # vem do AccountConfig.behavior.ai_memory_messages (caller).
    full_history: list[dict[str, Any]] = await history.load(ctx.thread_id)
    if memory_limit is not None and len(full_history) > memory_limit:
        raw_messages: list[dict[str, Any]] = list(full_history[-memory_limit:])
        history_prefix: list[dict[str, Any]] = list(full_history[:-memory_limit])
    else:
        raw_messages = list(full_history)
        history_prefix = []
    raw_messages.append({"role": "user", "content": user_message})

    forced_instruction: str | None = None
    if guard_service is not None:
        guard_result = guard_service.check(user_message, {"messages": raw_messages})
        if guard_result.blocked:
            log.info(
                "agent_guard_blocked",
                reason=guard_result.reason,
                thread_id=ctx.thread_id,
            )
            forced_instruction = guard_result.forced_instruction or None

    tool_defs: list[ChatCompletionToolParam] = registry.get_tools()

    for iteration in range(_MAX_ITERATIONS):
        system_prompt = build_system_prompt(long_term_facts, forced_instruction=forced_instruction)
        all_messages = cast(
            list[ChatCompletionMessageParam],
            [{"role": "system", "content": system_prompt}, *raw_messages],
        )
        # OpenAI SDK overloads are discriminated on `stream`; kwargs unpacking breaks
        # resolution — suppressing the single false-positive here.
        completion = await client.chat.completions.create(  # type: ignore[call-overload]
            model=model,
            messages=all_messages,
            **({"tools": tool_defs, "tool_choice": "auto"} if tool_defs else {}),
        )

        choice: Choice = completion.choices[0]
        assistant_msg: dict[str, Any] = choice.message.model_dump(mode="json", exclude_none=True)
        raw_messages.append(assistant_msg)
        AGENT_ITERATIONS.labels(outcome="iteration").inc()

        if choice.finish_reason != "tool_calls" or not choice.message.tool_calls:
            break

        fn_tool_calls: list[ChatCompletionMessageFunctionToolCall] = [
            tc
            for tc in choice.message.tool_calls
            if isinstance(tc, ChatCompletionMessageFunctionToolCall)
        ]
        log.debug(
            "agent_tools_dispatched",
            iteration=iteration,
            tools=[tc.function.name for tc in fn_tool_calls],
            thread_id=ctx.thread_id,
        )
        for tc in fn_tool_calls:
            AGENT_TOOL_CALLS.labels(tool_name=tc.function.name).inc()

        tool_msgs = await _dispatch_all(fn_tool_calls, registry, ctx)
        raw_messages.extend(tool_msgs)

        # Re-check guards after tool execution using updated message history
        if guard_service is not None:
            guard_result = guard_service.check("", {"messages": raw_messages})
            if guard_result.blocked:
                forced_instruction = guard_result.forced_instruction or None
            else:
                forced_instruction = None
    else:
        log.warning("agent_max_iterations_exceeded", thread_id=ctx.thread_id)
        AGENT_ITERATIONS.labels(outcome="max_iterations").inc()
        raw_messages.append({"role": "assistant", "content": _FALLBACK})

    # Reconstroi o histórico completo (prefix antigo + janela trabalhada agora)
    # para que o JSONB persista todas as mensagens, mesmo as fora do window.
    await history.save(ctx.thread_id, history_prefix + raw_messages)

    for msg in reversed(raw_messages):
        if msg.get("role") == "assistant" and msg.get("content"):
            return str(msg["content"])
    return _FALLBACK


async def _dispatch_all(
    tool_calls: list[ChatCompletionMessageFunctionToolCall],
    registry: ToolRegistry,
    ctx: AgentContext,
) -> list[dict[str, Any]]:
    """Execute all tool calls concurrently and return tool result messages."""

    async def _one(tc: ChatCompletionMessageFunctionToolCall) -> dict[str, Any]:
        try:
            args: dict[str, Any] = json.loads(tc.function.arguments or "{}")
            content = await registry.dispatch(tc.function.name, ctx, **args)
        except KeyError:
            log.warning("unknown_tool_called", name=tc.function.name)
            content = f"Ferramenta desconhecida: {tc.function.name}"
        except Exception as exc:
            log.error("tool_execution_error", tool=tc.function.name, error=str(exc), exc_info=True)
            content = f"Erro ao executar {tc.function.name}."
        return {"role": "tool", "tool_call_id": tc.id, "content": content}

    return list(await asyncio.gather(*(_one(tc) for tc in tool_calls)))
