from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FakeLLM:
    """Deterministic fake for tests. Maps prompts to canned responses."""

    json_responses: dict[str, dict[str, Any]] = field(default_factory=dict)
    text_responses: dict[str, str] = field(default_factory=dict)
    embeddings: list[list[float]] = field(default_factory=list)
    transcription: str = "transcribed text"
    calls: list[dict[str, Any]] = field(default_factory=list)

    async def complete_json(
        self,
        *,
        system: str,
        user: str,
        json_schema: dict[str, Any],
        temperature: float = 0.2,
    ) -> dict[str, Any]:
        self.calls.append({"kind": "json", "system": system, "user": user})
        for key, value in self.json_responses.items():
            if key in system or key in user:
                return value
        default = self.json_responses.get("default", {})
        if not default:
            raise RuntimeError(
                f"FakeLLM missing json response for user={user!r} system={system!r}"
            )
        return default

    async def complete_text(
        self,
        *,
        system: str,
        user: str,
        temperature: float = 0.7,
    ) -> str:
        self.calls.append({"kind": "text", "system": system, "user": user})
        for key, value in self.text_responses.items():
            if key == "default":
                continue
            if key in user or key in system:
                return value
        return self.text_responses.get("default", "")

    async def transcribe_audio(self, *, audio_bytes: bytes) -> str:
        self.calls.append({"kind": "transcribe", "bytes": len(audio_bytes)})
        return self.transcription

    async def embed(self, *, texts: list[str]) -> list[list[float]]:
        self.calls.append({"kind": "embed", "count": len(texts)})
        if self.embeddings:
            return self.embeddings[: len(texts)]
        return [[0.0] * 8 for _ in texts]
