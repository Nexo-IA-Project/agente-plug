from __future__ import annotations

from dataclasses import dataclass

from nexoia.domain.value_objects.sentiment import Sentiment


@dataclass
class FrustrationGuard:
    max_attempts: int = 2

    def should_escalate(self, *, sentiment: Sentiment, attempts: int) -> bool:
        return sentiment == Sentiment.HOSTILE and attempts >= self.max_attempts
