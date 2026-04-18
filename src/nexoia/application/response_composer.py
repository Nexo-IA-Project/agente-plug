from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from nexoia.application.communication_rules import CommunicationRules
from nexoia.domain.ports.llm import LLMPort
from nexoia.domain.value_objects.sentiment import Sentiment

_TONE_HINTS: dict[Sentiment, str] = {
    Sentiment.NEUTRAL: "Tom: prestativo e direto.",
    Sentiment.POSITIVE: "Tom: animado e acolhedor.",
    Sentiment.FRUSTRATED: "Tom: empático e calmo, reconhece a dificuldade.",
    Sentiment.ANGRY: "Tom: muito empático, evite qualquer tom defensivo.",
    Sentiment.ANXIOUS: "Tom: tranquilizador e seguro.",
    Sentiment.HOSTILE: "Tom: extremamente calmo, sem confronto, frase curta.",
}

_BASE_SYSTEM = (
    "Você é a assistente de suporte da NexoIA. "
    "Responda em PT-BR informal (vc, pra, tá). "
    "Máximo 300 caracteres. Sem bullets, negrito ou markdown. "
    "Nunca diga que é IA."
)


class CompositionError(RuntimeError):
    pass


@dataclass
class ResponseComposer:
    llm: LLMPort
    max_retries: int = 2
    rules: CommunicationRules = field(default_factory=CommunicationRules)

    def _tone_hint(self, sentiment: Sentiment) -> str:
        return _TONE_HINTS.get(sentiment, _TONE_HINTS[Sentiment.NEUTRAL])

    def _build_system(self, sentiment: Sentiment, violations: list | None = None) -> str:
        system = f"{_BASE_SYSTEM}\n{self._tone_hint(sentiment)}"
        if violations:
            system += f"\nAtenção: resposta anterior violou: {', '.join(v.value for v in violations)}. Corrija."
        return system

    async def compose(
        self,
        *,
        context_messages: list[dict[str, Any]],
        sentiment: Sentiment,
    ) -> str:
        user_text = next(
            (m["content"] for m in reversed(context_messages) if m.get("role") == "user"),
            "",
        )
        violations = None
        for _attempt in range(self.max_retries):
            system = self._build_system(sentiment, violations)
            text = await self.llm.complete_text(
                system=system, user=user_text, temperature=0.7
            )
            violations = self.rules.check(text)
            if not violations:
                return text
        raise CompositionError(
            f"Could not compose valid response after {self.max_retries} attempts. "
            f"Last violations: {violations}"
        )
