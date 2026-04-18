from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger(__name__)


async def run_welcome_subgraph(**kwargs: Any) -> dict[str, Any]:
    """Executa o subgraph Welcome. TODO: injetar deps reais via container DI."""
    from nexoia.application.capabilities.welcome import WelcomeState, build_welcome_subgraph
    graph = build_welcome_subgraph().compile()
    initial_state: WelcomeState = dict(kwargs)  # type: ignore[assignment]
    result = await graph.ainvoke(initial_state)
    return result


async def handle_process_purchase_webhook(payload: dict[str, Any]) -> None:
    log = logger.bind(
        handler="process_purchase",
        purchase_id=payload["purchase_id"],
        correlation_id=payload.get("correlation_id", ""),
    )
    log.info("handling_purchase_webhook")

    await run_welcome_subgraph(
        purchase_id=payload["purchase_id"],
        account_id=payload["account_id"],
        student_name=payload["student_name"],
        student_phone=payload["student_phone"],
        student_email=payload["student_email"],
        product_name=payload["product_name"],
        access_link=None,
        cademi_attempts=0,
        conversation_id=None,
        access_case_id=None,
        access_confirmed=False,
        cademi_failed=False,
        messages=[],
        correlation_id=payload.get("correlation_id", ""),
    )
    log.info("purchase_webhook_handled")
