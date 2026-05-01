from __future__ import annotations

from nexoia.application.use_cases.knowledge.stopwords_ptbr import STOPWORDS


class KeywordExtractor:
    def extract(self, query: str) -> list[str]:
        tokens = query.lower().split()
        return [t for t in tokens if t not in STOPWORDS and len(t) > 2]
