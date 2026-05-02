"""AgentContext — per-conversation context passed explicitly to every tool handler."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentContext:
    """Carries per-conversation identifiers through the OpenAI function calling loop.

    Replaces the LangGraph RunnableConfig["configurable"] pattern — all fields are
    explicit, no hidden injection.
    """

    account_id: str
    phone: str
    conversation_id: str
    thread_id: str
