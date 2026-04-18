from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum


class ViolationType(StrEnum):
    TOO_LONG = "too_long"
    FORBIDDEN_WORD = "forbidden_word"
    MARKDOWN = "markdown"
    IA_REVEAL = "ia_reveal"


_FORBIDDEN = re.compile(
    r"(?i)\b(putz|puts|poxa|que chato|entendo entendo)\b|Claro!"
)
_MARKDOWN = re.compile(r"(\*\*|\*|__|_|#{1,6} |- |\d+\. )")
_IA_REVEAL = re.compile(
    r"\b(sou (uma? )?ia|intelig[eê]ncia artificial|sou um (rob[ôo]|bot|assistente virtual))\b",
    re.IGNORECASE,
)
_MAX_CHARS = 300


@dataclass
class CommunicationRules:
    max_chars: int = _MAX_CHARS

    def check(self, text: str) -> list[ViolationType]:
        violations: list[ViolationType] = []
        if len(text) > self.max_chars:
            violations.append(ViolationType.TOO_LONG)
        if _FORBIDDEN.search(text):
            violations.append(ViolationType.FORBIDDEN_WORD)
        if _MARKDOWN.search(text):
            violations.append(ViolationType.MARKDOWN)
        if _IA_REVEAL.search(text):
            violations.append(ViolationType.IA_REVEAL)
        return violations
