from __future__ import annotations

from pydantic import BaseModel, Field


class PurchaseWebhookPayload(BaseModel):
    purchase_id: str
    nome: str
    email: str
    telefone: str
    produto: str
    valor: float
    timestamp: str = Field(..., description="ISO 8601")
    document: str | None = Field(default=None)
