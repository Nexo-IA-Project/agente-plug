from __future__ import annotations

import structlog

from interface.worker.handlers.hubla_event import handle_hubla_event

log = structlog.get_logger(__name__)


async def handle_purchase(payload: dict) -> None:
    """Worker job kind 'purchase' — legacy webhook /webhook/purchase.

    Delega para o pipeline unificado do HublaEventHandler, garantindo que
    trigger_event_type seja respeitado também neste caminho legado.

    O payload enviado pelo /webhook/purchase já contém "type" (o HublaEventParser
    valida que seja "subscription.activated"), portanto a delegação direta funciona.
    Se por algum motivo o campo estiver ausente, sintetizamos o valor padrão.
    """
    if "type" not in payload:
        payload = {**payload, "type": "subscription.activated"}
        log.warning("legacy_purchase_payload_missing_type_field_synthesized")

    log.info("legacy_purchase_routed_to_hubla_event_handler", event_type=payload.get("type"))
    await handle_hubla_event(payload)
