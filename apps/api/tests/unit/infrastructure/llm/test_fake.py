from nexoia.infrastructure.llm.fake_client import FakeLLM


async def test_complete_json_returns_canned() -> None:
    fake = FakeLLM(
        json_responses={"classify": {"intent": "access", "confidence": 0.92}}
    )
    result = await fake.complete_json(
        system="classify intents",
        user="nao consigo entrar",
        json_schema={},
    )
    assert result == {"intent": "access", "confidence": 0.92}


async def test_complete_text_returns_canned() -> None:
    fake = FakeLLM(text_responses={"default": "Olá!"})
    text = await fake.complete_text(system="", user="oi")
    assert text == "Olá!"


async def test_fake_records_calls() -> None:
    fake = FakeLLM(text_responses={"default": "ok"})
    await fake.complete_text(system="s", user="u")
    assert fake.calls[0]["kind"] == "text"
    assert fake.calls[0]["user"] == "u"
