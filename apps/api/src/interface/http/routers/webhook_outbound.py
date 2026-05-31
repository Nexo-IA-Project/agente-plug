"""POST /webhook/outbound — plataformas externas enviam mensagens via Nexos Flow.

Autenticação: Bearer <api_token> (mesmo sistema de tokens do painel admin).
A mensagem é entregue ao contato via ChatNexo sem acionar loop de IA.
"""
from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from cryptography.fernet import Fernet
from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from shared.adapters.agent_selection.random_selection import RandomAgentSelection
from shared.adapters.chatnexo.agent_picker import build_chatnexo_client
from shared.adapters.db.repositories.account_config_repo import AccountConfigRepository
from shared.adapters.db.session import session_scope
from shared.adapters.observability.logger import get_logger
from shared.config.settings import get_settings
from shared.config.single_tenant import get_default_account_uuid

router = APIRouter(tags=["webhook"])
log = get_logger(__name__)


@dataclass
class _Config:
    token_validator: Callable[[str], Awaitable[bool]] | None = None


_cfg = _Config()


def configure(*, token_validator: Callable[[str], Awaitable[bool]]) -> None:
    _cfg.token_validator = token_validator


class OutboundMessageRequest(BaseModel):
    phone: str
    text: str
    conversation_id: str | None = None
    origin: str = "external"
    metadata: dict[str, Any] = Field(default_factory=dict)


async def _require_token(request: Request) -> None:
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = auth.removeprefix("Bearer ").strip()
    if _cfg.token_validator is None or not await _cfg.token_validator(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post("/webhook/outbound", status_code=status.HTTP_202_ACCEPTED)
async def send_outbound(request: Request, body: OutboundMessageRequest) -> dict[str, Any]:
    """Recebe uma mensagem de uma plataforma externa e a entrega ao contato via ChatNexo.

    Não aciona loop de IA — apenas envia o texto fornecido.
    """
    await _require_token(request)

    message_id = f"nxo_{uuid.uuid4().hex[:16]}"

    s = get_settings()
    fernet = Fernet(s.integration_credentials_key.encode())

    async with session_scope() as session:
        account_uuid = await get_default_account_uuid(session)
        config_repo = AccountConfigRepository(session=session, fernet=fernet)
        config = await config_repo.get(account_id=account_uuid)

    i = config.integration
    chatnexo, _ = build_chatnexo_client(
        base_url=i.chatnexo_base_url,
        agents=i.chatnexo_agents,
        strategy=RandomAgentSelection(),
        fallback_api_key=i.chatnexo_api_key,
    )

    try:
        conversation_id = body.conversation_id
        if not conversation_id:
            conversation_id = await chatnexo.get_open_conversation(
                str(i.chatnexo_account_id), body.phone
            )
        if not conversation_id:
            conversation_id = await chatnexo.create_conversation(
                str(i.chatnexo_account_id),
                body.phone,
                inbox_id=i.chatnexo_inbox_id,
            )

        await chatnexo.send_message(
            account_id=str(i.chatnexo_account_id),
            conversation_id=str(conversation_id),
            text=body.text,
        )
    except Exception as exc:
        log.error("outbound_chatnexo_error", error=str(exc), phone=body.phone, origin=body.origin)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="failed to deliver message via chatnexo",
        ) from exc

    log.info(
        "outbound_message_sent",
        message_id=message_id,
        phone=body.phone,
        conversation_id=conversation_id,
        origin=body.origin,
    )

    return {
        "accepted": True,
        "message_id": message_id,
        "conversation_id": str(conversation_id),
        "status": "sent",
    }
