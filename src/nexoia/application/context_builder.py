from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from nexoia.domain.entities.message import Message, MessageSource


@dataclass
class ContextBuilder:
    """Builds LLM-ready message list from conversation history.

    Critical rule: messages sent by human operators MUST NOT be presented as
    the AI's own assistant turns. They are flagged as user turns with a marker.
    """

    def build_llm_messages(
        self,
        history: list[Message],
        *,
        long_term_facts: dict[str, Any] | None = None,
    ) -> list[dict[str, str]]:
        system_lines = ["Você é a IA de suporte da NexoIA."]
        if long_term_facts:
            for k, v in long_term_facts.items():
                system_lines.append(f"{k}: {v}")
        messages: list[dict[str, str]] = [
            {"role": "system", "content": "\n".join(system_lines)}
        ]
        for msg in history:
            if msg.source == MessageSource.STUDENT:
                messages.append({"role": "user", "content": msg.content})
            elif msg.source == MessageSource.AGENT_IA:
                messages.append({"role": "assistant", "content": msg.content})
            elif msg.source == MessageSource.AGENT_HUMAN:
                messages.append(
                    {"role": "user", "content": f"[operador humano]: {msg.content}"}
                )
        return messages
