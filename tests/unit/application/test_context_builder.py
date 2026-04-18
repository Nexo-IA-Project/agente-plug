from uuid import uuid4

from nexoia.application.context_builder import ContextBuilder
from nexoia.domain.entities.message import Message, MessageDirection, MessageSource


def _msg(source: MessageSource, direction: MessageDirection, content: str) -> Message:
    return Message(
        id=uuid4(),
        conversation_id=uuid4(),
        direction=direction,
        source=source,
        content=content,
    )


def test_builds_llm_messages_with_role_separation() -> None:
    history = [
        _msg(MessageSource.STUDENT, MessageDirection.IN, "olá"),
        _msg(MessageSource.AGENT_IA, MessageDirection.OUT, "oi, posso ajudar"),
        _msg(MessageSource.AGENT_HUMAN, MessageDirection.OUT, "[humano] segue link"),
        _msg(MessageSource.STUDENT, MessageDirection.IN, "obrigado"),
    ]
    builder = ContextBuilder()
    out = builder.build_llm_messages(history, long_term_facts={"email": "a@b"})

    assert out[0]["role"] == "system"
    assert "email: a@b" in out[0]["content"].lower()
    assert out[1] == {"role": "user", "content": "olá"}
    assert out[2] == {"role": "assistant", "content": "oi, posso ajudar"}
    # human messages go as user with marker to avoid LLM confusing them as its own
    assert out[3] == {"role": "user", "content": "[operador humano]: [humano] segue link"}
    assert out[4] == {"role": "user", "content": "obrigado"}
