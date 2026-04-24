from __future__ import annotations

from nexoia.domain.policies.guards import GuardResult


class FrustrationGuard:
    """Stub — lógica de detecção de hostilidade a implementar no futuro."""

    def check(self, message: str, state: dict) -> GuardResult:
        return GuardResult(blocked=False)
