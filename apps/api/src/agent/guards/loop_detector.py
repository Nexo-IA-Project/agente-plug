from __future__ import annotations

from agent.guards import GuardResult

_THRESHOLD = 3


class LoopDetectorGuard:
    def check(self, message: str, state: dict) -> GuardResult:
        recent_ai = [
            str(m.get("content", ""))
            for m in state.get("messages", [])[-6:]
            if isinstance(m, dict) and m.get("role") == "assistant" and m.get("content")
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
