from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from typing import Any, TypedDict

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
ACCESS_FREE_TEXT = (
    "Tudo certo! Aqui tá seu acesso, {name} — é só clicar que já entra direto: {link}"
)
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
    log = logger.bind(
        capability="access", node="lookup_access_case", account_id=state["account_id"]
    )
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
    log = logger.bind(
        capability="access", node="check_platform_scope", account_id=state["account_id"]
    )
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


async def node_search_cademi_cascade(
    state: AccessState,
    *,
    cademi_port: Any,
    chatnexo_port: Any,
    handoff_fn: Callable[..., Awaitable[None]],
) -> dict[str, Any]:
    log = logger.bind(
        capability="access",
        node="search_cademi_cascade",
        account_id=state["account_id"],
        access_case_id=state.get("access_case_id"),
    )

    if state.get("out_of_scope") or state.get("access_case_id") is None:
        return {}

    # Email mismatch detection
    email_from_msg = _extract_email_from_last_message(state)
    stored_email = state.get("student_email")
    if (
        email_from_msg
        and stored_email
        and email_from_msg.lower() != stored_email.lower()
        and not state.get("email_mismatch_pending", False)
    ):
        await chatnexo_port.send_message(
            account_id=state["account_id"],
            conversation_id=state.get("conversation_id"),
            text=EMAIL_MISMATCH_MESSAGE,
        )
        return {"email_mismatch_pending": True}

    attempts = state.get("search_attempts", 0)

    # Attempt 1: email
    if attempts < 1:
        email_to_try = email_from_msg or stored_email
        if email_to_try:
            log.info("attempt_email", attempt=1)
            student = await cademi_port.get_student_by_email(email_to_try)
            attempts = 1
            if student is not None:
                return {"cademi_student": student, "search_attempts": attempts}

    # Attempt 2: CPF
    if attempts < 2:
        current_cpf = state.get("student_cpf")
        cpf_from_msg = _extract_cpf_from_last_message(state)
        if current_cpf is None and cpf_from_msg:
            current_cpf = cpf_from_msg

        if current_cpf is None and not state.get("cpf_asked", False):
            await chatnexo_port.send_message(
                account_id=state["account_id"],
                conversation_id=state.get("conversation_id"),
                text=CPF_REQUEST_MESSAGE,
            )
            return {"cpf_asked": True, "search_attempts": attempts}

        if current_cpf is None:
            return {"cpf_asked": True, "search_attempts": attempts}

        log.info("attempt_cpf", attempt=2)
        student = await cademi_port.get_student_by_cpf(current_cpf)
        attempts = 2
        if student is not None:
            return {
                "cademi_student": student,
                "search_attempts": attempts,
                "student_cpf": current_cpf,
            }

    # Attempt 3: name+phone
    if attempts < CADEMI_MAX_ATTEMPTS:
        log.info("attempt_name_phone", attempt=3)
        try:
            student = await cademi_port.get_student_by_name_phone(
                name=state.get("student_name") or "",
                phone=state["student_phone"],
            )
        except NotImplementedError:
            student = None
        attempts = CADEMI_MAX_ATTEMPTS
        if student is not None:
            return {"cademi_student": student, "search_attempts": attempts}

    log.warning("cademi_exhausted", reason="cademi_not_found_after_3_attempts")
    await handoff_fn(
        account_id=state["account_id"],
        conversation_id=state.get("conversation_id"),
        reason="cademi_not_found_after_3_attempts",
    )
    return {"cademi_student": None, "search_attempts": attempts}


async def node_send_access(
    state: AccessState,
    *,
    cademi_port: Any,
    chatnexo_port: Any,
) -> dict[str, Any]:
    log = logger.bind(
        capability="access",
        node="send_access",
        account_id=state["account_id"],
        access_case_id=state.get("access_case_id"),
    )

    if (
        state.get("out_of_scope")
        or state.get("access_case_id") is None
        or state.get("cademi_student") is None
    ):
        return {}

    student: CademiStudent = state["cademi_student"]  # type: ignore[assignment]
    product_id = state.get("purchase_id") or ""
    link = await cademi_port.get_access_link(student_id=student.id, product_id=product_id)

    within_24h = bool(state.get("within_24h_window", False))
    if within_24h:
        first_name = (student.name or "").split()[0] if student.name else ""
        text = ACCESS_FREE_TEXT.format(name=first_name, link=link)
        await chatnexo_port.send_message(
            account_id=state["account_id"],
            conversation_id=state.get("conversation_id"),
            text=text,
        )
    else:
        await chatnexo_port.send_template(
            account_id=state["account_id"],
            conversation_id=state.get("conversation_id"),
            template_name=ACCESS_RESEND_TEMPLATE,
            variables={"1": student.name or "", "2": state.get("product_name") or "", "3": link},
        )
    log.info("access_sent", within_24h=within_24h)
    return {"access_link": link}


async def node_update_access_case(
    state: AccessState,
    *,
    access_case_repo: Any,
) -> dict[str, Any]:
    log = logger.bind(
        capability="access",
        node="update_access_case",
        account_id=state["account_id"],
        access_case_id=state.get("access_case_id"),
    )

    if state.get("access_case_id") is None or state.get("out_of_scope"):
        return {}
    if state.get("cpf_asked") and state.get("cademi_student") is None:
        return {}
    if state.get("email_mismatch_pending"):
        return {}

    attempts = state.get("search_attempts", 0)
    if state.get("access_link") and state.get("cademi_student") is not None:
        new_status = AccessCaseStatus.REACTIVE_LINK_SENT
    else:
        new_status = AccessCaseStatus.REACTIVE_ESCALATED

    await access_case_repo.update_status(
        case_id=state["access_case_id"],
        status=new_status,
        search_attempts=attempts,
    )
    log.info("access_case_updated", new_status=new_status.value)
    return {}


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
