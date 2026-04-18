from __future__ import annotations

from dataclasses import dataclass

from nexoia.domain.ports.llm import LLMPort
from nexoia.domain.value_objects.sentiment import Sentiment
from nexoia.infrastructure.llm.prompts import sentiment as prompt


@dataclass
class SentimentDetector:
    llm: LLMPort

    async def detect(self, *, text: str) -> Sentiment:
        result = await self.llm.complete_json(
            system=prompt.SYSTEM_PROMPT,
            user=text,
            json_schema=prompt.SCHEMA,
            temperature=0.0,
        )
        try:
            return Sentiment(result.get("sentiment", "neutral"))
        except ValueError:
            return Sentiment.NEUTRAL
