from __future__ import annotations

import re
from dataclasses import dataclass

_FORBIDDEN = re.compile(r"(?i)\b(putz|puts|poxa|que chato|entendo entendo)\b|Claro!")
_MARKDOWN = re.compile(r"(\*\*|\*|__|_|#{1,6} |- |\d+\. )")
_IA_REVEAL = re.compile(
    r"\b(sou (uma? )?ia|intelig[eê]ncia artificial|sou um (rob[ôo]|bot|assistente virtual))\b",
    re.IGNORECASE,
)
MAX_CHARS = 300


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    correction_hint: str = ""


class CommunicationRules:
    def validate(self, content: str) -> ValidationResult:
        if len(content) > MAX_CHARS:
            return ValidationResult(
                ok=False,
                correction_hint=f"Resposta muito longa ({len(content)} chars). Máximo {MAX_CHARS}. Reescreva de forma mais curta.",
            )
        if _FORBIDDEN.search(content):
            return ValidationResult(
                ok=False,
                correction_hint="Palavra proibida detectada. Reescreva sem expressões informais negativas.",
            )
        if _MARKDOWN.search(content):
            return ValidationResult(
                ok=False,
                correction_hint="Sem markdown. WhatsApp não renderiza formatação. Reescreva em texto simples.",
            )
        if _IA_REVEAL.search(content):
            return ValidationResult(
                ok=False,
                correction_hint="Não revele que é uma IA. Reescreva sem mencionar inteligência artificial ou robô.",
            )
        return ValidationResult(ok=True)
