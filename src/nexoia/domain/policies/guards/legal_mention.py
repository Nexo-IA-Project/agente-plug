from __future__ import annotations

import re

from nexoia.domain.policies.guards import GuardResult

_KEYWORDS = [
    "procon",
    "advogad",
    "processo judicial",
    "ação judicial",
    "jurídic",
    "juridic",
    "reclame aqui",
    "justiça",
    "consumidor.gov",
]
_PATTERN = re.compile("|".join(_KEYWORDS), re.IGNORECASE)


class LegalMentionGuard:
    def check(self, message: str, state: dict) -> GuardResult:
        if _PATTERN.search(message):
            return GuardResult(
                blocked=True,
                reason="legal_mention",
                skill_override="escalar_para_humano",
            )
        return GuardResult(blocked=False)
