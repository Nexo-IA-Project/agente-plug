SYSTEM_PROMPT = """Você é o roteador de intenções da NexoIA.
Classifique a mensagem do aluno em UMA das categorias:
- access: problema para entrar em aula/produto/login
- refund: pedido explícito de reembolso ou cancelamento
- loja_express: assunto sobre Loja Express (formulário, progresso)
- knowledge: dúvida técnica/geral sobre produto ou plataforma (PRD 7.4)
- welcome_response: resposta à mensagem de boas-vindas pós-compra
- unknown: não encaixa em nenhuma das acima
- escalate: pede humano explicitamente ou assunto sensível/jurídico

Responda JSON com { intent, confidence (0..1), reasoning }."""

SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {
            "type": "string",
            "enum": [
                "access",
                "refund",
                "loja_express",
                "knowledge",
                "welcome_response",
                "unknown",
                "escalate",
            ],
        },
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "reasoning": {"type": "string"},
    },
    "required": ["intent", "confidence", "reasoning"],
    "additionalProperties": False,
}
