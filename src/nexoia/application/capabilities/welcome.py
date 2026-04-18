from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, TypedDict

import structlog

from nexoia.domain.entities.access_case import AccessCase, AccessCaseStatus
from nexoia.domain.errors import CademiError
from nexoia.domain.ports.cademi_port import CademiPort

logger = structlog.get_logger(__name__)

_CADEMI_MAX_RETRIES = 3
_CADEMI_RETRY_BASE_SECONDS = 1.0
_GENERIC_ACCESS_MESSAGE = "em instantes você receberá seu link de acesso"


class WelcomeState(TypedDict, total=False):
    purchase_id: str
    account_id: int
    student_name: str
    student_phone: str
    student_email: str
    product_name: str
    access_link: str | None
    cademi_attempts: int
    conversation_id: str | None
    access_case_id: str | None
    access_confirmed: bool
    cademi_failed: bool
    messages: list
    correlation_id: str


async def node_fetch_cademi(
    state: WelcomeState,
    *,
    cademi_port: CademiPort,
    handoff_fn: Callable[..., Awaitable[None]] | None = None,
    _retry_delay: float | None = None,  # injectable for tests (pass 0.0 to skip sleep)
) -> dict[str, Any]:
    log = logger.bind(node="fetch_cademi", purchase_id=state.get("purchase_id"))
    retry_delay = _retry_delay if _retry_delay is not None else _CADEMI_RETRY_BASE_SECONDS

    for attempt in range(1, _CADEMI_MAX_RETRIES + 1):
        try:
            student = await cademi_port.get_student_by_email(state["student_email"])
            if student is None:
                log.warning("student_not_found", email=state["student_email"])
                return {"cademi_failed": True, "access_link": None, "cademi_attempts": attempt}

            access_link = await cademi_port.get_access_link(
                student_id=student.id,
                product_id=state["purchase_id"],
            )
            log.info("cademi_link_fetched", attempt=attempt)
            return {"access_link": access_link, "cademi_failed": False, "cademi_attempts": attempt}

        except CademiError as exc:
            log.warning("cademi_error", attempt=attempt, error=str(exc))
            if attempt < _CADEMI_MAX_RETRIES:
                await asyncio.sleep(retry_delay * (3 ** (attempt - 1)))

    log.warning("cademi_exhausted")
    if handoff_fn is not None:
        await handoff_fn(
            account_id=state.get("account_id"),
            conversation_id=state.get("conversation_id"),
            reason="cademi_unavailable",
        )
    return {"cademi_failed": True, "access_link": None, "cademi_attempts": _CADEMI_MAX_RETRIES}


async def node_check_conversation(
    state: WelcomeState,
    *,
    chatnexo_port: Any,
) -> dict[str, Any]:
    existing = await chatnexo_port.get_open_conversation(
        account_id=state["account_id"],
        contact_phone=state["student_phone"],
    )
    if existing:
        return {"conversation_id": existing}

    new_conv = await chatnexo_port.create_conversation(
        account_id=state["account_id"],
        contact_phone=state["student_phone"],
    )
    return {"conversation_id": new_conv}


async def node_send_welcome(
    state: WelcomeState,
    *,
    chatnexo_port: Any,
) -> dict[str, Any]:
    link = state.get("access_link") or _GENERIC_ACCESS_MESSAGE
    await chatnexo_port.send_template(
        account_id=state["account_id"],
        conversation_id=state["conversation_id"],
        template_name="welcome_purchase",
        variables={
            "1": state["student_name"],
            "2": state["product_name"],
            "3": link,
        },
    )
    return {}


async def node_persist_access_case(
    state: WelcomeState,
    *,
    access_case_repo: Any,
) -> dict[str, Any]:
    case = AccessCase(
        account_id=state["account_id"],
        contact_id=state["student_email"],
        conversation_id=state["conversation_id"],
        purchase_id=state["purchase_id"],
        product_name=state["product_name"],
        access_link=state.get("access_link"),
        status=AccessCaseStatus.ESCALATED if state.get("cademi_failed") else AccessCaseStatus.LINK_SENT,
    )
    await access_case_repo.save(case)
    return {"access_case_id": case.id}


async def node_schedule_d1(
    state: WelcomeState,
    *,
    scheduler: Any,
    d1_delay_hours: int = 24,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    job = await scheduler.schedule(
        job_type="SendScheduledFollowUp",
        payload={
            "template": "access_reminder_d1",
            "access_case_id": state.get("access_case_id"),
            "account_id": state.get("account_id"),
            "conversation_id": state.get("conversation_id"),
        },
        run_at=now + timedelta(hours=d1_delay_hours),
    )
    return {"scheduled_d1_job_id": job.id}


def build_welcome_subgraph():
    from langgraph.graph import END, StateGraph
    graph = StateGraph(WelcomeState)
    graph.add_node("fetch_cademi", node_fetch_cademi)
    graph.add_node("check_conversation", node_check_conversation)
    graph.add_node("send_welcome", node_send_welcome)
    graph.add_node("persist_access_case", node_persist_access_case)
    graph.add_node("schedule_d1", node_schedule_d1)
    graph.set_entry_point("fetch_cademi")
    graph.add_edge("fetch_cademi", "check_conversation")
    graph.add_edge("check_conversation", "send_welcome")
    graph.add_edge("send_welcome", "persist_access_case")
    graph.add_edge("persist_access_case", "schedule_d1")
    graph.add_edge("schedule_d1", END)
    return graph
