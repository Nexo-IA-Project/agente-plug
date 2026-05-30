from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from openai import AsyncOpenAI


@dataclass
class OpenAIClient:
    client: AsyncOpenAI
    chat_model: str = "gpt-4o-mini"
    embed_model: str = "text-embedding-3-small"

    # A chave OpenAI agora vem da config global de plataforma — construa o cliente
    # via resolve_openai_key(session) (shared.application.resolve_openai_key), não
    # de get_settings(). Por isso não há mais from_settings().

    async def complete_json(
        self,
        *,
        system: str,
        user: str,
        json_schema: dict[str, Any],
        temperature: float = 0.2,
    ) -> dict[str, Any]:
        resp = await self.client.chat.completions.create(
            model=self.chat_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {"name": "structured", "schema": json_schema, "strict": True},
            },
            temperature=temperature,
        )
        content = resp.choices[0].message.content or "{}"
        return json.loads(content)

    async def complete_text(
        self,
        *,
        system: str,
        user: str,
        temperature: float = 0.7,
    ) -> str:
        resp = await self.client.chat.completions.create(
            model=self.chat_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
        )
        return resp.choices[0].message.content or ""

    async def embed(self, *, texts: list[str]) -> list[list[float]]:
        resp = await self.client.embeddings.create(model=self.embed_model, input=texts)
        return [d.embedding for d in resp.data]
