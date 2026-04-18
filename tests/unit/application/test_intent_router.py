from nexoia.application.intent_router import IntentDecision, IntentRouter
from nexoia.domain.value_objects.intent import Intent
from nexoia.infrastructure.llm.fake_client import FakeLLM


async def test_router_selects_capability_with_high_confidence() -> None:
    fake = FakeLLM(
        json_responses={
            "default": {"intent": "access", "confidence": 0.92, "reasoning": "ok"}
        }
    )
    router = IntentRouter(llm=fake, confidence_threshold=0.7)
    decision = await router.classify(user_text="nao consigo entrar")
    assert decision.intent == Intent.ACCESS
    assert decision.confidence == 0.92
    assert decision.should_escalate is False


async def test_router_escalates_below_threshold() -> None:
    fake = FakeLLM(
        json_responses={"default": {"intent": "access", "confidence": 0.4, "reasoning": "dúvida"}}
    )
    router = IntentRouter(llm=fake, confidence_threshold=0.7)
    decision = await router.classify(user_text="olá")
    assert decision.should_escalate is True


async def test_router_escalates_on_explicit_intent() -> None:
    fake = FakeLLM(
        json_responses={"default": {"intent": "escalate", "confidence": 0.95, "reasoning": ""}}
    )
    router = IntentRouter(llm=fake, confidence_threshold=0.7)
    decision = await router.classify(user_text="quero falar com humano")
    assert decision.should_escalate is True
