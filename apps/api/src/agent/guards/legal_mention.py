from __future__ import annotations

import re

from agent.guards import GuardResult

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
                forced_instruction=(
                    "INSTRUÇÃO CRÍTICA: O aluno mencionou ação legal ou órgão de defesa do consumidor. "
                    "Você DEVE chamar imediatamente a skill escalar_para_humano. "
                    "Não responda por texto — use a skill."
                ),
            )
        return GuardResult(blocked=False)
