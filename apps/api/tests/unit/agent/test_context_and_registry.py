"""Unit tests for AgentContext and ToolRegistry (Task 1)."""
from __future__ import annotations

import pytest

from agent.context import AgentContext
from agent.tool_registry import ToolRegistry


# ── AgentContext ──────────────────────────────────────────────────────────────


def test_agent_context_fields_are_stored():
    ctx = AgentContext(
        account_id="acc-1",
        phone="+5511999999999",
        conversation_id="conv-abc",
        thread_id="thread-xyz",
    )
    assert ctx.account_id == "acc-1"
    assert ctx.phone == "+5511999999999"
    assert ctx.conversation_id == "conv-abc"
    assert ctx.thread_id == "thread-xyz"


def test_agent_context_is_immutable():
    ctx = AgentContext(
        account_id="acc-1",
        phone="+5511999999999",
        conversation_id="conv-abc",
        thread_id="thread-xyz",
    )
    with pytest.raises(Exception):
        ctx.account_id = "other"  # type: ignore[misc]


# ── ToolRegistry ──────────────────────────────────────────────────────────────

_PARAMS = {
    "type": "object",
    "properties": {"query": {"type": "string"}},
    "required": ["query"],
}


async def _my_handler(ctx: AgentContext, query: str) -> str:
    return f"result:{ctx.account_id}:{query}"


def _make_registry() -> ToolRegistry:
    reg = ToolRegistry()
    reg.register(
        name="my_tool",
        description="A test tool",
        parameters=_PARAMS,
        handler=_my_handler,
    )
    return reg


def test_registry_len_after_register():
    reg = _make_registry()
    assert len(reg) == 1


def test_registry_contains():
    reg = _make_registry()
    assert "my_tool" in reg
    assert "other_tool" not in reg


def test_get_tools_returns_openai_format():
    reg = _make_registry()
    tools = reg.get_tools()
    assert len(tools) == 1
    t = tools[0]
    assert t["type"] == "function"
    assert t["function"]["name"] == "my_tool"
    assert t["function"]["description"] == "A test tool"
    assert t["function"]["parameters"] == _PARAMS


def test_get_handler_returns_callable():
    reg = _make_registry()
    h = reg.get_handler("my_tool")
    assert callable(h)


def test_get_handler_raises_for_unknown():
    reg = _make_registry()
    with pytest.raises(KeyError, match="no_such_tool"):
        reg.get_handler("no_such_tool")


def test_register_duplicate_raises():
    reg = _make_registry()
    with pytest.raises(ValueError, match="already registered"):
        reg.register(
            name="my_tool",
            description="duplicate",
            parameters=_PARAMS,
            handler=_my_handler,
        )


@pytest.mark.asyncio
async def test_dispatch_calls_handler_with_context():
    ctx = AgentContext(
        account_id="acc-99",
        phone="+55",
        conversation_id="c1",
        thread_id="t1",
    )
    reg = _make_registry()
    result = await reg.dispatch("my_tool", ctx, query="hello")
    assert result == "result:acc-99:hello"


@pytest.mark.asyncio
async def test_dispatch_unknown_tool_raises():
    ctx = AgentContext(
        account_id="acc-1",
        phone="+55",
        conversation_id="c1",
        thread_id="t1",
    )
    reg = ToolRegistry()
    with pytest.raises(KeyError):
        await reg.dispatch("nonexistent", ctx)
