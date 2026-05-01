from nexoia.domain.value_objects.intent import Intent
from nexoia.domain.value_objects.priority import Priority
from nexoia.domain.value_objects.sentiment import Sentiment


def test_intent_values() -> None:
    assert Intent.ACCESS.value == "access"
    assert Intent.REFUND.value == "refund"
    assert Intent.LOJA_EXPRESS.value == "loja_express"
    assert Intent.KNOWLEDGE.value == "knowledge"
    assert Intent.WELCOME_RESPONSE.value == "welcome_response"
    assert Intent.UNKNOWN.value == "unknown"
    assert Intent.ESCALATE.value == "escalate"


def test_sentiment_values() -> None:
    assert Sentiment.NEUTRAL.value == "neutral"
    assert Sentiment.POSITIVE.value == "positive"
    assert Sentiment.FRUSTRATED.value == "frustrated"
    assert Sentiment.ANGRY.value == "angry"
    assert Sentiment.ANXIOUS.value == "anxious"
    assert Sentiment.HOSTILE.value == "hostile"


def test_priority_order() -> None:
    assert Priority.URGENT.score < Priority.HIGH.score
    assert Priority.HIGH.score < Priority.NORMAL.score
    assert Priority.NORMAL.score < Priority.LOW.score
