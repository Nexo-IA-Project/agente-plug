"""Unit tests for runner.py — mocked OpenAI client and session."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from agent.context import AgentContext
from agent.guards import GuardResult, GuardService
from agent.runner import _FALLBACK, run_agent
from agent.tool_registry import ToolRegistry

# ── helpers ───────────────────────────────────────────────────────────────────


def _make_ctx() -> AgentContext:
    return AgentContext(
        account_id="acc-1",
        phone="+5511999999999",
        conversation_id="conv-abc",
        thread_id="thread-xyz",
    )


def _mock_session(stored_messages: list | None = None) -> AsyncMock:
    """Return a minimal SQLAlchemy AsyncSession mock for ConversationHistory."""
    result = MagicMock()
    row = MagicMock()
    row.messages = stored_messages or []
    result.scalar_one_or_none = MagicMock(return_value=row if stored_messages else None)

    session = AsyncMock()
    session.execute = AsyncMock(return_value=result)
    return session


def _make_completion(content: str, tool_calls: list | None = None) -> MagicMock:
    """Build a mock ChatCompletion response."""
    msg = MagicMock()
    msg.content = content
    msg.tool_calls = tool_calls
    msg.model_dump = MagicMock(return_value={"role": "assistant", "content": content})

    choice = MagicMock()
    choice.message = msg
    choice.finish_reason = "tool_calls" if tool_calls else "stop"

    completion = MagicMock()
    completion.choices = [choice]
    return completion


def _make_tool_call(name: str, arguments: str, call_id: str = "tc-1") -> MagicMock:
    fn = MagicMock()
    fn.name = name
    fn.arguments = arguments

    tc = MagicMock()
    tc.function = fn
    tc.id = call_id
    return tc


def _make_client(*completions: MagicMock) -> AsyncMock:
    client = AsyncMock()
    client.chat.completions.create = AsyncMock(side_effect=list(completions))
    return client


# ── basic text response ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_returns_assistant_text_on_stop():
    client = _make_client(_make_completion("Olá, tudo bem?"))
    ctx = _make_ctx()
    session = _mock_session()
    registry = ToolRegistry()

    reply = await run_agent(
        ctx=ctx,
        user_message="Oi",
        registry=registry,
        session=session,
        client=client,
        model="gpt-4o-mini",
    )

    assert reply == "Olá, tudo bem?"


@pytest.mark.asyncio
async def test_history_is_loaded_and_saved():
    stored = [{"role": "user", "content": "mensagem anterior"}]
    client = _make_client(_make_completion("Resposta"))
    ctx = _make_ctx()
    session = _mock_session(stored)
    registry = ToolRegistry()

    await run_agent(
        ctx=ctx,
        user_message="nova mensagem",
        registry=registry,
        session=session,
        client=client,
        model="gpt-4o-mini",
    )

    # execute was called at least twice: once to load, once for upsert in save
    assert session.execute.await_count >= 2


# ── tool call dispatching ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_tool_call_is_dispatched_and_result_appended():
    async def _handler(ctx: AgentContext, phone: str) -> str:
        return f"resultado:{phone}"

    registry = ToolRegistry()
    registry.register(
        name="buscar_aluno",
        description="Busca aluno",
        parameters={
            "type": "object",
            "properties": {"phone": {"type": "string"}},
            "required": ["phone"],
        },
        handler=_handler,
    )

    tc = _make_tool_call("buscar_aluno", '{"phone": "+55"}', call_id="tc-42")
    first_completion = _make_completion("", tool_calls=[tc])
    first_completion.choices[0].message.model_dump = MagicMock(
        return_value={"role": "assistant", "content": "", "tool_calls": [{"id": "tc-42"}]}
    )
    second_completion = _make_completion("Aluno encontrado!")

    client = _make_client(first_completion, second_completion)
    ctx = _make_ctx()
    session = _mock_session()

    reply = await run_agent(
        ctx=ctx,
        user_message="busca aí",
        registry=registry,
        session=session,
        client=client,
        model="gpt-4o-mini",
    )

    assert reply == "Aluno encontrado!"
    # Two OpenAI calls: one with tool_calls, one after tool result
    assert client.chat.completions.create.await_count == 2


@pytest.mark.asyncio
async def test_unknown_tool_returns_error_content():
    tc = _make_tool_call("ferramenta_inexistente", "{}")
    first_completion = _make_completion("", tool_calls=[tc])
    first_completion.choices[0].message.model_dump = MagicMock(
        return_value={"role": "assistant", "content": ""}
    )
    second_completion = _make_completion("Não consegui.")

    client = _make_client(first_completion, second_completion)
    ctx = _make_ctx()
    session = _mock_session()
    registry = ToolRegistry()

    # Should not raise — unknown tool returns error content to OpenAI
    reply = await run_agent(
        ctx=ctx,
        user_message="teste",
        registry=registry,
        session=session,
        client=client,
        model="gpt-4o-mini",
    )

    assert reply == "Não consegui."


# ── max iterations guard ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fallback_returned_when_max_iterations_exceeded():
    async def _handler(ctx: AgentContext) -> str:
        return "resultado"

    registry = ToolRegistry()
    registry.register(
        name="loop_tool",
        description="Tool that always requests another call",
        parameters={"type": "object", "properties": {}},
        handler=_handler,
    )

    tc = _make_tool_call("loop_tool", "{}")

    # Every completion triggers a tool_call (simulates infinite loop)
    completions = []
    for _ in range(10):
        c = _make_completion("", tool_calls=[tc])
        c.choices[0].message.model_dump = MagicMock(
            return_value={"role": "assistant", "content": ""}
        )
        completions.append(c)

    client = _make_client(*completions)
    ctx = _make_ctx()
    session = _mock_session()

    reply = await run_agent(
        ctx=ctx,
        user_message="loop",
        registry=registry,
        session=session,
        client=client,
        model="gpt-4o-mini",
    )

    assert reply == _FALLBACK
    assert client.chat.completions.create.await_count == 10


# ── guard integration ─────────────────────────────────────────────────────────


def _make_blocking_guard(forced: str) -> GuardService:
    class _BlockGuard:
        def check(self, message: str, state: dict) -> GuardResult:
            return GuardResult(blocked=True, reason="test", forced_instruction=forced)

    return GuardService([_BlockGuard()])


def _make_pass_guard() -> GuardService:
    class _PassGuard:
        def check(self, message: str, state: dict) -> GuardResult:
            return GuardResult(blocked=False)

    return GuardService([_PassGuard()])


@pytest.mark.asyncio
async def test_blocked_guard_injects_forced_instruction_into_system_prompt():
    captured_messages: list = []

    async def _create(**kwargs):  # type: ignore[no-untyped-def]
        captured_messages.extend(kwargs.get("messages", []))
        return _make_completion("escalei")

    client = AsyncMock()
    client.chat.completions.create = _create

    guard_service = _make_blocking_guard("INSTRUÇÃO: escalar agora")
    ctx = _make_ctx()
    session = _mock_session()
    registry = ToolRegistry()

    await run_agent(
        ctx=ctx,
        user_message="ameaça legal",
        registry=registry,
        session=session,
        client=client,
        guard_service=guard_service,
        model="gpt-4o-mini",
    )

    system = next((m for m in captured_messages if m.get("role") == "system"), None)
    assert system is not None
    assert "INSTRUÇÃO: escalar agora" in system["content"]


@pytest.mark.asyncio
async def test_pass_guard_does_not_inject_forced_instruction():
    captured_messages: list = []

    async def _create(**kwargs):  # type: ignore[no-untyped-def]
        captured_messages.extend(kwargs.get("messages", []))
        return _make_completion("tudo certo")

    client = AsyncMock()
    client.chat.completions.create = _create

    ctx = _make_ctx()
    session = _mock_session()
    registry = ToolRegistry()

    await run_agent(
        ctx=ctx,
        user_message="preciso de ajuda",
        registry=registry,
        session=session,
        client=client,
        guard_service=_make_pass_guard(),
        model="gpt-4o-mini",
    )

    system = next((m for m in captured_messages if m.get("role") == "system"), None)
    assert system is not None
    assert "INSTRUÇÃO PRIORITÁRIA" not in system["content"]
