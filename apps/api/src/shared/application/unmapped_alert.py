from __future__ import annotations

from collections.abc import Awaitable, Callable

import structlog

log = structlog.get_logger(__name__)


def make_unmapped_alert(
    *, chatnexo, account_id: str, inbox_id: int, target: str | None
) -> Callable[[str, str, str, str], Awaitable[None]]:
    """Retorna um hook async que avisa, via ChatNexo, sobre produto não reconhecido.

    No-op se `target` não estiver configurado. Nunca levanta (alerta não pode
    derrubar o pipeline de eventos).
    """

    async def _alert(
        product_name: str, hubla_product_id: str, payer_name: str, payer_phone: str
    ) -> None:
        if not target:
            return
        text = (
            "⚠️ Produto não reconhecido no onboarding\n"
            f"Produto: {product_name or '(sem nome)'}\n"
            f"ID Hubla não cadastrado: {hubla_product_id}\n"
            f"Lead: {payer_name} {payer_phone}\n"
            "Cadastre esse ID em Produtos (ou na aba Pendências) para destravar o funil."
        )
        try:
            conversation_id = await chatnexo.get_open_conversation(
                account_id=account_id, contact_phone=target
            )
            if conversation_id is None:
                conversation_id = await chatnexo.create_conversation(
                    account_id=account_id,
                    contact_phone=target,
                    inbox_id=inbox_id,
                )
            await chatnexo.send_message(
                account_id=account_id, conversation_id=str(conversation_id), text=text
            )
        except Exception as exc:
            log.warning("unmapped_alert_failed", error=str(exc))

    return _alert
