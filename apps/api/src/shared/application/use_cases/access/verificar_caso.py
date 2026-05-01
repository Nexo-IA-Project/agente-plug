from __future__ import annotations

from typing import Any

import structlog

from nexoia.domain.ports.chatnexo import ChatNexoPort

log = structlog.get_logger(__name__)

_OUT_OF_SCOPE_KEYWORDS = ("shopee", "kyc")


class VerificarCasoAcesso:
    def __init__(self, repo: Any, chatnexo: ChatNexoPort) -> None:
        self._repo = repo
        self._chatnexo = chatnexo

    async def execute(self, account_id: str, phone: str, last_message: str) -> str:
        case = await self._repo.find_by_phone(account_id=account_id, phone=phone)

        if case is None:
            log.warning("no_access_case", account_id=account_id)
            await self._chatnexo.transfer_to_human(
                account_id=account_id,
                conversation_id=None,
                reason="no_access_case",
            )
            return "ESCALADO: Caso de acesso não encontrado para este número."

        if any(kw in last_message.lower() for kw in _OUT_OF_SCOPE_KEYWORDS):
            log.warning("out_of_scope", account_id=account_id, reason="shopee_or_kyc")
            await self._chatnexo.transfer_to_human(
                account_id=account_id,
                conversation_id=None,
                reason="shopee_or_kyc_out_of_scope",
            )
            return "ESCALADO: Solicitação fora do escopo (Shopee/KYC)."

        return (
            f"CASO_ENCONTRADO: case_id={case.id}, "
            f"tentativas={case.search_attempts}, "
            f"email_cadastrado={case.student_email}"
        )
