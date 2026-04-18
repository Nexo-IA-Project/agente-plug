SYSTEM_PROMPT = (
    "Classifique o sentimento do aluno. "
    "Retorne JSON com campo 'sentiment' em "
    "[neutral, positive, frustrated, angry, anxious, hostile]."
)

SCHEMA = {
    "type": "object",
    "properties": {
        "sentiment": {
            "type": "string",
            "enum": ["neutral", "positive", "frustrated", "angry", "anxious", "hostile"],
        }
    },
    "required": ["sentiment"],
    "additionalProperties": False,
}
