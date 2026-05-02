# apps/api/src/agent/skills/buscar_conhecimento/synonym_expander.py
"""Expande keywords com sinônimos para melhorar o recall da busca RAG."""

from __future__ import annotations

_SYNONYMS: dict[str, list[str]] = {
    "acesso": ["login", "entrar", "acessar", "senha"],
    "reembolso": ["devolução", "estorno", "cancelamento", "devolver"],
    "curso": ["treinamento", "aula", "módulo", "conteúdo"],
    "certificado": ["diploma", "certificação"],
    "pagamento": ["cobrança", "fatura", "boleto", "pix", "cartão"],
    "suporte": ["ajuda", "atendimento", "assistência"],
}


def expand_synonyms(keywords: list[str]) -> list[str]:
    """Retorna os keywords originais mais seus sinônimos conhecidos, sem duplicatas."""
    expanded: list[str] = list(keywords)
    seen = set(keywords)
    for kw in keywords:
        for syn in _SYNONYMS.get(kw, []):
            if syn not in seen:
                seen.add(syn)
                expanded.append(syn)
    return expanded
