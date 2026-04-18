from nexoia.application.sentiment import SentimentDetector
from nexoia.domain.value_objects.sentiment import Sentiment
from nexoia.infrastructure.llm.fake_client import FakeLLM


async def test_detects_frustrated() -> None:
    fake = FakeLLM(json_responses={"default": {"sentiment": "frustrated"}})
    detector = SentimentDetector(llm=fake)
    result = await detector.detect(text="isso nao esta funcionando faz 2 dias")
    assert result == Sentiment.FRUSTRATED


async def test_unknown_value_falls_back_to_neutral() -> None:
    fake = FakeLLM(json_responses={"default": {"sentiment": "gibberish"}})
    detector = SentimentDetector(llm=fake)
    assert await detector.detect(text="oi") == Sentiment.NEUTRAL
