from __future__ import annotations

import re
from datetime import datetime, UTC
from typing import Any, Awaitable, Callable, TypedDict

import structlog
from langgraph.graph import END, StateGraph

from nexoia.domain.entities.access_case import AccessCaseStatus
from nexoia.domain.ports.cademi_port import CademiStudent

logger = structlog.get_logger(__name__)

CADEMI_MAX_ATTEMPTS = 3
CPF_REQUEST_MESSAGE = "Pra eu te ajudar mais rápido, me passa seu CPF (só números, por favor)?"
EMAIL_MISMATCH_MESSAGE = (
    "Percebi que o email que vc passou é diferente do cadastro da compra. "
    "Quer que eu atualize pra esse novo email antes de reenviar o acesso?"
)
ACCESS_FREE_TEXT = "Tudo certo! Aqui tá seu acesso, {name} — é só clicar que já entra direto: {link}"
ACCESS_RESEND_TEMPLATE = "access_reminder_d1"
_OUT_OF_SCOPE_KEYWORDS = ("shopee", "kyc")
_EMAIL_REGEX = re.compile(r"[\w.\-\+]+@[\w\-]+(?:\.[\w\-]+)+")
_CPF_REGEX = re.compile(r"\d{3}\.?\d{3}\.?\d{3}\-?\d{2}")


class AccessState(TypedDict, total=False):
    account_id: int
    correlation_id: str
    messages: list
    access_case_id: str | None
    student_email: str | None
    student_cpf: str | None
    student_name: str | None
    student_phone: str | None
    cademi_student: CademiStudent | None
    search_attempts: int
    cpf_asked: bool
    access_link: str | None
    out_of_scope: bool
    email_mismatch_pending: bool
    conversation_id: str | None
    purchase_id: str | None
    product_name: str | None
    within_24h_window: bool | None


def _extract_last_user_message(state: AccessState) -> str:
    messages = state.get("messages") or []
    for msg in reversed(messages):
        if msg.get("role") == "user":
            return str(msg.get("content", ""))
    return ""


def _normalize_cpf(raw: str) -> str:
    digits = re.sub(r"\D", "", raw)
    return digits if len(digits) == 11 else ""


def _extract_email_from_last_message(state: AccessState) -> str | None:
    msg = _extract_last_user_message(state)
    match = _EMAIL_REGEX.search(msg)
    return match.group(0).lower() if match else None


def _extract_cpf_from_last_message(state: AccessState) -> str | None:
    msg = _extract_last_user_message(state)
    match = _CPF_REGEX.search(msg)
    if match is None:
        return None
    return _normalize_cpf(match.group(0)) or None


async def node_lookup_access_case(
    state: AccessState,
    *,
    access_case_repo: Any,
    chatnexo_port: Any,
    handoff_fn: Callable[..., Awaitable[None]],
) -> dict[str, Any]:
    log = logger.bind(capability="access", node="lookup_access_case", account_id=state["account_id"])
    case = await access_case_repo.find_by_phone(
        account_id=state["account_id"],
        phone=state["student_phone"],
    )
    if case is None:
        log.warning("no_access_case")
        await handoff_fn(
            account_id=state["account_id"],
            conversation_id=state.get("conversation_id"),
            reason="no_access_case",
        )
        return {"access_case_id": None}
    log.info("access_case_found", access_case_id=case.id)
    return {
        "access_case_id": case.id,
        "student_cpf": case.student_cpf,
        "student_email": state.get("student_email"),
        "student_name": state.get("student_name"),
        "search_attempts": case.search_attempts,
    }


async def node_check_platform_scope(
    state: AccessState,
    *,
    handoff_fn: Callable[..., Awaitable[None]],
) -> dict[str, Any]:
    log = logger.bind(capability="access", node="check_platform_scope", account_id=state["account_id"])
    if state.get("access_case_id") is None:
        return {}
    last_msg = _extract_last_user_message(state).lower()
    if any(kw in last_msg for kw in _OUT_OF_SCOPE_KEYWORDS):
        log.warning("out_of_scope", reason="shopee_or_kyc_out_of_scope")
        await handoff_fn(
            account_id=state["account_id"],
            conversation_id=state.get("conversation_id"),
            reason="shopee_or_kyc_out_of_scope",
        )
        return {"out_of_scope": True}
    return {"out_of_scope": False}


async def node_search_cademi_cascade(state: AccessState, **deps: Any) -> dict[str, Any]:
    raise NotImplementedError("Task 9")


async def node_send_access(state: AccessState, **deps: Any) -> dict[str, Any]:
    raise NotImplementedError("Task 10")


async def node_update_access_case(state: AccessState, **deps: Any) -> dict[str, Any]:
    raise NotImplementedError("Task 11")


def build_access_subgraph() -> StateGraph:
    graph = StateGraph(AccessState)
    graph.add_node("lookup_access_case", node_lookup_access_case)
    graph.add_node("check_platform_scope", node_check_platform_scope)
    graph.add_node("search_cademi_cascade", node_search_cademi_cascade)
    graph.add_node("send_access", node_send_access)
    graph.add_node("update_access_case", node_update_access_case)
    graph.set_entry_point("lookup_access_case")
    graph.add_edge("lookup_access_case", "check_platform_scope")
    graph.add_edge("check_platform_scope", "search_cademi_cascade")
    graph.add_edge("search_cademi_cascade", "send_access")
    graph.add_edge("send_access", "update_access_case")
    graph.add_edge("update_access_case", END)
    return graph
