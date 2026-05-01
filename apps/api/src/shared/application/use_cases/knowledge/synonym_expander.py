from __future__ import annotations

SYNONYMS: dict[str, list[str]] = {
    "acessar":     ["entrar", "logar", "fazer login", "abrir"],
    "senha":       ["palavra-chave", "credencial", "password"],
    "curso":       ["treinamento", "aula", "conteúdo", "material"],
    "certificado": ["diploma", "certificação", "conclusão"],
    "módulo":      ["aula", "lição", "capítulo", "unidade"],
    "plataforma":  ["sistema", "portal", "ambiente"],
    "cancelar":    ["desistir", "sair", "encerrar"],
    "atualizar":   ["renovar", "fazer upgrade"],
    "pagamento":   ["cobrar", "cobrança", "fatura", "boleto", "pix"],
    "download":    ["baixar", "salvar", "exportar"],
    "suporte":     ["ajuda", "atendimento", "contato"],
    "vídeo":       ["aula gravada", "conteúdo", "material"],
    "ao vivo":     ["live", "aula ao vivo", "transmissão"],
    "grupo":       ["comunidade", "turma", "whatsapp"],
    "mentoria":    ["acompanhamento", "coaching", "consulta"],
}


class SynonymExpander:
    def expand(self, query: str) -> str:
        if not query:
            return query
        words = query.lower().split()
        extra: list[str] = []
        for w in words:
            if w in SYNONYMS:
                extra.extend(SYNONYMS[w])
        return f"{query} {' '.join(extra)}" if extra else query
