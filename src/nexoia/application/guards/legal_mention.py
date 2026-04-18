from __future__ import annotations

import re
from dataclasses import dataclass

_KEYWORDS = [
    "procon",
    "advogad",
    "processo",
    "ação judicial",
    "juridic",
    "reclame aqui",
    "justiça",
]

_PATTERN = re.compile("|".join(_KEYWORDS), re.IGNORECASE)


@dataclass
class LegalMentionGuard:
    def should_escalate(self, text: str) -> bool:
        return bool(_PATTERN.search(text))
