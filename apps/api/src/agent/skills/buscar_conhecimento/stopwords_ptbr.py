# apps/api/src/agent/skills/buscar_conhecimento/stopwords_ptbr.py
"""Stopwords em português brasileiro para uso no keyword extractor."""
from __future__ import annotations

STOPWORDS: frozenset[str] = frozenset({
    "a", "ao", "aos", "aquela", "aquelas", "aquele", "aqueles", "aquilo",
    "as", "até", "com", "como", "da", "das", "de", "dela", "delas", "dele",
    "deles", "depois", "do", "dos", "e", "ela", "elas", "ele", "eles", "em",
    "entre", "era", "essa", "essas", "esse", "esses", "esta", "estas", "este",
    "estes", "eu", "foi", "for", "foram", "há", "isso", "isto", "já", "lhe",
    "lhes", "mais", "mas", "me", "mesmo", "meu", "meus", "minha", "minhas",
    "muito", "na", "nas", "nem", "no", "nos", "nós", "num", "numa", "o", "os",
    "ou", "para", "pela", "pelas", "pelo", "pelos", "por", "qual", "quando",
    "que", "quem", "se", "seu", "seus", "só", "sua", "suas", "também", "te",
    "tem", "têm", "teu", "teus", "tua", "tuas", "um", "uma", "umas", "uns",
    "você", "vocês",
})
