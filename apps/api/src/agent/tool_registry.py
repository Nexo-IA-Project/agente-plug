"""ToolRegistry — manages OpenAI function calling tool definitions and handlers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from openai.types.chat import ChatCompletionToolParam

from agent.context import AgentContext

Handler = Callable[..., Awaitable[str]]


@dataclass
class _ToolEntry:
    definition: ChatCompletionToolParam
    handler: Handler


class ToolRegistry:
    """Registry of OpenAI-compatible tool definitions and their async handlers.

    Usage:
        registry = ToolRegistry()
        registry.register(
            name="my_tool",
            description="Does something useful",
            parameters={"type": "object", "properties": {"x": {"type": "string"}}, "required": ["x"]},
            handler=my_async_fn,
        )
        tools = registry.get_tools()   # pass to openai client
        await registry.dispatch("my_tool", ctx, x="hello")
    """

    def __init__(self) -> None:
        self._entries: dict[str, _ToolEntry] = {}

    def register(
        self,
        *,
        name: str,
        description: str,
        parameters: dict[str, Any],
        handler: Handler,
    ) -> None:
        """Register a tool with its OpenAI schema and async handler."""
        if name in self._entries:
            raise ValueError(f"Tool '{name}' is already registered")
        definition: ChatCompletionToolParam = {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": parameters,
            },
        }
        self._entries[name] = _ToolEntry(definition=definition, handler=handler)

    def get_tools(self) -> list[ChatCompletionToolParam]:
        """Return all tool definitions in OpenAI format for use in API calls."""
        return [entry.definition for entry in self._entries.values()]

    def get_handler(self, name: str) -> Handler:
        """Return the async handler for a given tool name."""
        try:
            return self._entries[name].handler
        except KeyError:
            raise KeyError(f"No tool registered with name '{name}'") from None

    async def dispatch(self, name: str, ctx: AgentContext, **kwargs: Any) -> str:
        """Call the handler for *name*, injecting *ctx* as the first argument."""
        handler = self.get_handler(name)
        return await handler(ctx, **kwargs)

    def __len__(self) -> int:
        return len(self._entries)

    def __contains__(self, name: object) -> bool:
        return name in self._entries
