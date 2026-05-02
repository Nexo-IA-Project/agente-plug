# apps/api/src/agent/skills/buscar_conhecimento/keyword_extractor.py
"""Extrai keywords relevantes de uma query em português brasileiro."""

from __future__ import annotations

import re

from agent.skills.buscar_conhecimento.stopwords_ptbr import STOPWORDS

_MIN_LENGTH = 3


def extract_keywords(query: str) -> list[str]:
    """Remove stopwords e retorna tokens únicos com >= 3 caracteres."""
    tokens = re.findall(r"\b[a-záéíóúàâêôãõüç]+\b", query.lower())
    seen: set[str] = set()
    keywords: list[str] = []
    for tok in tokens:
        if tok not in STOPWORDS and len(tok) >= _MIN_LENGTH and tok not in seen:
            seen.add(tok)
            keywords.append(tok)
    return keywords
