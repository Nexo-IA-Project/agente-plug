"""OpenAI function calling agent loop.

Replaces the LangGraph-based graph.py / react_node.py with a direct, transparent
implementation that has no framework dependencies beyond the OpenAI SDK.
"""

from __future__ import annotations

import asyncio
import json
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
from agent.history import ConversationHistory
from agent.prompt import build_system_prompt
from agent.tool_registry import ToolRegistry

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
    model: str = "gpt-4o",
) -> str:
    """Run the agent loop for one user turn. Returns the assistant's final reply."""
    history = ConversationHistory(session=session)
    raw_messages: list[dict[str, Any]] = await history.load(ctx.thread_id)
    raw_messages.append({"role": "user", "content": user_message})

    system_prompt = build_system_prompt(long_term_facts or [])
    tool_defs: list[ChatCompletionToolParam] = registry.get_tools()

    for iteration in range(_MAX_ITERATIONS):
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

        if choice.finish_reason != "tool_calls" or not choice.message.tool_calls:
            break

        # Filter to function tool calls only — custom tool calls don't have .function
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
        tool_msgs = await _dispatch_all(fn_tool_calls, registry, ctx)
        raw_messages.extend(tool_msgs)
    else:
        log.warning("agent_max_iterations_exceeded", thread_id=ctx.thread_id)
        raw_messages.append({"role": "assistant", "content": _FALLBACK})

    await history.save(ctx.thread_id, raw_messages)

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
