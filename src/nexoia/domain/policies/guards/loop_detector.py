from __future__ import annotations

from langchain_core.messages import AIMessage

from nexoia.domain.policies.guards import GuardResult

_THRESHOLD = 3


class LoopDetectorGuard:
    def check(self, message: str, state: dict) -> GuardResult:
        recent_ai = [
            str(m.content)
            for m in state.get("messages", [])[-6:]
            if isinstance(m, AIMessage)
        ]
        tail = recent_ai[-_THRESHOLD:]
        if len(tail) >= _THRESHOLD and len(set(tail)) == 1:
            return GuardResult(
                blocked=True,
                reason="loop_detected",
                forced_instruction=(
                    "INSTRUÇÃO CRÍTICA: Foi detectado um loop de respostas repetidas. "
                    "Você DEVE chamar imediatamente a skill escalar_para_humano. "
                    "Não responda por texto — use a skill."
                ),
            )
        return GuardResult(blocked=False)
