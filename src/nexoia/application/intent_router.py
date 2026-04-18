from __future__ import annotations

from dataclasses import dataclass

from nexoia.domain.ports.llm import LLMPort
from nexoia.domain.value_objects.intent import Intent
from nexoia.application.prompts import intent_classifier as prompt


@dataclass(frozen=True, slots=True)
class IntentDecision:
    intent: Intent
    confidence: float
    reasoning: str

    @property
    def should_escalate(self) -> bool:
        return self.intent == Intent.ESCALATE


@dataclass
class IntentRouter:
    llm: LLMPort
    confidence_threshold: float = 0.7

    async def classify(self, *, user_text: str) -> IntentDecision:
        result = await self.llm.complete_json(
            system=prompt.SYSTEM_PROMPT,
            user=user_text,
            json_schema=prompt.SCHEMA,
            temperature=0.0,
        )
        intent = Intent(result.get("intent", Intent.UNKNOWN.value))
        confidence = float(result.get("confidence", 0.0))
        reasoning = str(result.get("reasoning", ""))
        if confidence < self.confidence_threshold:
            intent = Intent.ESCALATE
        return IntentDecision(intent=intent, confidence=confidence, reasoning=reasoning)


_INTENT_TO_NODE: dict[str, str] = {
    "welcome": "capability_welcome",
    "access": "capability_access",
    "refund": "capability_refund",
    "loja_express": "capability_loja_express",
    "knowledge": "capability_knowledge",
}


def route_to_capability(intent: str) -> str:
    """Return the main-graph node name for the given intent."""
    return _INTENT_TO_NODE.get(intent, "capability_knowledge")
