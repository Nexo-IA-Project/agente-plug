import pytest

from nexoia.application.response_composer import CompositionError, ResponseComposer
from nexoia.domain.value_objects.sentiment import Sentiment
from nexoia.infrastructure.llm.fake_client import FakeLLM


async def test_composer_returns_valid_response():
    fake = FakeLLM(text_responses={"default": "oi, tudo bem?"})
    composer = ResponseComposer(llm=fake, max_retries=2)
    result = await composer.compose(
        context_messages=[{"role": "user", "content": "oi"}],
        sentiment=Sentiment.NEUTRAL,
    )
    assert result == "oi, tudo bem?"


async def test_composer_retries_on_violation_and_succeeds():
    # First response violates (too long), second is valid
    responses = ["a" * 301, "ok, entendido!"]
    call_count = 0

    class RetryFakeLLM:
        async def complete_text(self, *, system, user, temperature=0.7):
            nonlocal call_count
            r = responses[call_count]
            call_count += 1
            return r

    composer = ResponseComposer(llm=RetryFakeLLM(), max_retries=2)
    result = await composer.compose(
        context_messages=[{"role": "user", "content": "oi"}],
        sentiment=Sentiment.NEUTRAL,
    )
    assert result == "ok, entendido!"
    assert call_count == 2


async def test_composer_raises_after_max_retries():
    fake = FakeLLM(text_responses={"default": "a" * 301})
    composer = ResponseComposer(llm=fake, max_retries=2)
    with pytest.raises(CompositionError):
        await composer.compose(
            context_messages=[{"role": "user", "content": "oi"}],
            sentiment=Sentiment.NEUTRAL,
        )


def test_tone_hint_varies_by_sentiment():
    composer = ResponseComposer(llm=FakeLLM(), max_retries=1)
    neutral = composer._tone_hint(Sentiment.NEUTRAL)
    hostile = composer._tone_hint(Sentiment.HOSTILE)
    assert neutral != hostile
