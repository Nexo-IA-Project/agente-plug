"""Unit tests for BaseSkill and register_skill adapter (Task 4)."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel

from agent.context import AgentContext
from agent.skill import BaseSkill, register_skill
from agent.tool_registry import ToolRegistry


# ── helpers ───────────────────────────────────────────────────────────────────


class _PhoneInput(BaseModel):
    phone: str


class _SearchInput(BaseModel):
    query: str
    limit: int = 5


class _LookupSkill(BaseSkill):
    @property
    def name(self) -> str:
        return "lookup_user"

    @property
    def description(self) -> str:
        return "Look up a user by phone number."

    def params_model(self) -> type[BaseModel]:
        return _PhoneInput

    async def handle(self, ctx: AgentContext, **kwargs: Any) -> str:
        return f"user:{ctx.account_id}:{kwargs['phone']}"


class _SearchSkill(BaseSkill):
    @property
    def name(self) -> str:
        return "search_kb"

    @property
    def description(self) -> str:
        return "Search the knowledge base."

    def params_model(self) -> type[BaseModel]:
        return _SearchInput

    async def handle(self, ctx: AgentContext, **kwargs: Any) -> str:
        return f"results:{kwargs['query']}"


def _make_ctx() -> AgentContext:
    return AgentContext(
        account_id="acc-1",
        phone="+55",
        conversation_id="conv-1",
        thread_id="t-1",
    )


# ── tool_definition ───────────────────────────────────────────────────────────


def test_tool_definition_has_correct_name_and_description():
    skill = _LookupSkill()
    defn = skill.tool_definition()
    assert defn["type"] == "function"
    assert defn["function"]["name"] == "lookup_user"
    assert defn["function"]["description"] == "Look up a user by phone number."


def test_tool_definition_schema_derived_from_pydantic():
    skill = _LookupSkill()
    params = skill.tool_definition()["function"]["parameters"]
    assert params["type"] == "object"
    assert "phone" in params["properties"]
    assert params["required"] == ["phone"]


def test_tool_definition_no_title_in_schema():
    skill = _LookupSkill()
    params = skill.tool_definition()["function"]["parameters"]
    assert "title" not in params


def test_tool_definition_optional_fields_reflected():
    skill = _SearchSkill()
    params = skill.tool_definition()["function"]["parameters"]
    assert "query" in params["properties"]
    assert "limit" in params["properties"]
    # only required is query (limit has default)
    assert "query" in params.get("required", [])
    assert "limit" not in params.get("required", [])


# ── register_skill adapter ────────────────────────────────────────────────────


def test_register_skill_adds_to_registry():
    registry = ToolRegistry()
    register_skill(registry, _LookupSkill())
    assert "lookup_user" in registry
    assert len(registry) == 1


def test_register_skill_tool_definition_in_registry():
    registry = ToolRegistry()
    register_skill(registry, _LookupSkill())
    tools = registry.get_tools()
    assert tools[0]["function"]["name"] == "lookup_user"


def test_register_multiple_skills():
    registry = ToolRegistry()
    register_skill(registry, _LookupSkill())
    register_skill(registry, _SearchSkill())
    assert len(registry) == 2
    assert "search_kb" in registry


# ── handle dispatch via registry ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_handle_called_via_registry_dispatch():
    registry = ToolRegistry()
    register_skill(registry, _LookupSkill())
    ctx = _make_ctx()

    result = await registry.dispatch("lookup_user", ctx, phone="+5511999")

    assert result == "user:acc-1:+5511999"


@pytest.mark.asyncio
async def test_handle_with_optional_param():
    registry = ToolRegistry()
    register_skill(registry, _SearchSkill())
    ctx = _make_ctx()

    result = await registry.dispatch("search_kb", ctx, query="reembolso")

    assert result == "results:reembolso"
