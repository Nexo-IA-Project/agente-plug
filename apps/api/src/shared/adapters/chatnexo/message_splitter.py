from __future__ import annotations

import re


def split_message(text: str, max_chars: int = 400, min_chars: int = 80) -> list[str]:
    """Quebra texto em partes menores para envio humanizado via WhatsApp.

    Estratégia:
    1. Se tem \\n\\n → quebra por parágrafo
    2. Cada parágrafo > max_chars → subdivide por sentença
    3. Se não tem \\n\\n → retorna [text] inteiro, qualquer tamanho
    4. Partes de subdivisão por sentença < min_chars → descartadas
    5. Se todos descartados → retorna [text] original (fallback)
    """
    stripped = text.strip()
    if not stripped:
        return []

    if "\n\n" not in stripped:
        # Sem parágrafos: retorna inteiro, qualquer tamanho
        return [stripped]

    # Com parágrafos
    paragraphs = [p.strip() for p in stripped.split("\n\n") if p.strip()]

    parts: list[str] = []
    has_been_split = False

    for para in paragraphs:
        if len(para) <= max_chars:
            # Parágrafo pequeno o bastante, mantém como está
            parts.append(para)
        else:
            # Parágrafo grande, subdivide por sentença
            has_been_split = True
            sub_parts = _split_by_sentence(para, max_chars)
            filtered_sub = [p for p in sub_parts if len(p) >= min_chars]
            if filtered_sub:
                parts.extend(filtered_sub)
            else:
                # Se nenhuma sub-parte passou no filtro, mantém o parágrafo original
                parts.append(para)

    # Aplica min_chars filter
    filtered = [p for p in parts if len(p) >= min_chars]
    if filtered:
        return filtered

    # Se nenhuma parte passa no min_chars, retorna original
    return [stripped]


def _split_by_sentence(text: str, max_chars: int) -> list[str]:
    # Quebra por sentença: . ? ! seguido de espaço/fim de string
    sentences = re.split(r"(?<=[.?!])\s+", text)
    sentences = [s for s in sentences if s]  # Remove strings vazias

    groups: list[str] = []
    current = ""

    for sentence in sentences:
        candidate = (current + " " + sentence).strip() if current else sentence
        if current and len(candidate) > max_chars:
            # Candidate excederia max_chars, então save current e inicie novo
            groups.append(current)
            current = sentence
        else:
            current = candidate

    if current:
        groups.append(current)

    return groups
