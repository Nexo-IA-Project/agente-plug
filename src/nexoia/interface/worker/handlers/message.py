from __future__ import annotations

from nexoia.infrastructure.observability.logger import get_logger

log = get_logger(__name__)


async def handle_message(payload: dict) -> None:
    """Stub handler for incoming ChatNexo messages.

    Specs ②–⑤ expandem este handler com o Main Graph LangGraph.
    """
    log.info(
        "message_job_received_stub",
        chatnexo_message_id=payload.get("chatnexo_message_id"),
    )
