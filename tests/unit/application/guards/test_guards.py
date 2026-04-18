import pytest

from nexoia.application.guards.frustration import FrustrationGuard
from nexoia.application.guards.legal_mention import LegalMentionGuard
from nexoia.application.guards.loop_detector import LoopDetectorGuard
from nexoia.domain.value_objects.sentiment import Sentiment


@pytest.mark.parametrize(
    "text,expected",
    [
        ("vou entrar com o procon", True),
        ("vou acionar meu advogado", True),
        ("isso vai dar processo", True),
        ("ação judicial pode ser melhor", True),
        ("tudo bem, vamos resolver", False),
    ],
)
def test_legal_guard_triggers_on_mentions(text: str, expected: bool) -> None:
    guard = LegalMentionGuard()
    assert guard.should_escalate(text) is expected


def test_loop_detector_triggers_after_n_identical_replies() -> None:
    guard = LoopDetectorGuard(threshold=3)
    replies = ["Posso ajudar?", "Posso ajudar?", "Posso ajudar?"]
    assert guard.is_looping(replies) is True


def test_loop_detector_not_triggered_when_under_threshold() -> None:
    guard = LoopDetectorGuard(threshold=3)
    assert guard.is_looping(["a", "b", "c"]) is False


def test_frustration_guard_triggers_on_hostile_plus_attempts() -> None:
    guard = FrustrationGuard(max_attempts=2)
    assert guard.should_escalate(sentiment=Sentiment.HOSTILE, attempts=2) is True
    assert guard.should_escalate(sentiment=Sentiment.NEUTRAL, attempts=5) is False
    assert guard.should_escalate(sentiment=Sentiment.HOSTILE, attempts=1) is False
