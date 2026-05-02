"""BaseSkill — abstract base class for OpenAI function-calling skills.

Every skill subclasses BaseSkill and declares:
- name / description: tool metadata
- params_model(): Pydantic model that describes the tool's inputs
- handle(): async business logic, receives AgentContext + validated kwargs
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from openai.types.chat import ChatCompletionToolParam
from pydantic import BaseModel

from agent.context import AgentContext
from agent.tool_registry import ToolRegistry


class BaseSkill(ABC):
    """Abstract base for a single OpenAI function-calling skill.

    Subclasses must implement name, description, params_model, and handle.
    tool_definition() is derived automatically from params_model().
    """

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def description(self) -> str: ...

    @abstractmethod
    def params_model(self) -> type[BaseModel]:
        """Return the Pydantic model that defines this skill's input parameters."""
        ...

    @abstractmethod
    async def handle(self, ctx: AgentContext, **kwargs: Any) -> str:
        """Execute the skill. Receives validated kwargs from the tool call."""
        ...

    def tool_definition(self) -> ChatCompletionToolParam:
        """Build the OpenAI function tool definition from params_model's JSON schema."""
        schema = self.params_model().model_json_schema()
        schema.pop("title", None)
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": schema,
            },
        }


def register_skill(registry: ToolRegistry, skill: BaseSkill) -> None:
    """Register a BaseSkill into a ToolRegistry.

    Extracts the tool definition and binds skill.handle as the handler.
    """
    defn = skill.tool_definition()
    fn = defn["function"]
    registry.register(
        name=str(fn["name"]),
        description=str(fn["description"]),
        parameters=dict(fn.get("parameters") or {}),
        handler=skill.handle,
    )
