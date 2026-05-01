from __future__ import annotations

import re
from typing import Any

import structlog

from nexoia.domain.ports.cademi_port import CademiPort

log = structlog.get_logger(__name__)

_CPF_REGEX = re.compile(r"\d{3}\.?\d{3}\.?\d{3}\-?\d{2}")
CADEMI_MAX_ATTEMPTS = 3


def _normalize_cpf(raw: str) -> str:
    digits = re.sub(r"\D", "", raw)
    return digits if len(digits) == 11 else ""


class BuscarAlunoCademi:
    def __init__(self, repo: Any, cademi: CademiPort) -> None:
        self._repo = repo
        self._cademi = cademi

    async def execute(
        self,
        account_id: str,
        phone: str,
        email: str | None = None,
        cpf: str | None = None,
        student_name: str | None = None,
    ) -> str:
        case = await self._repo.find_by_phone(account_id=account_id, phone=phone)
        if case is None:
            return "CASO_NAO_ENCONTRADO: Nenhum caso de acesso ativo para este número."

        attempts = case.search_attempts

        if attempts >= CADEMI_MAX_ATTEMPTS:
            return (
                "ESCALADO: Limite de 3 tentativas atingido. "
                "Transferindo para atendimento humano."
            )

        # Tentativa 1 — email
        if attempts < 1 and email:
            email_to_try = email or case.student_email
            if email_to_try:
                student = await self._cademi.get_student_by_email(email_to_try)
                if student:
                    await self._repo.update_status(
                        case_id=case.id,
                        status="REACTIVE_LINK_SENT",
                        search_attempts=1,
                    )
                    log.info("cademi_found_email", account_id=account_id)
                    return f"ENCONTRADO: {student.name} (email). student_id={student.id}"

        # Tentativa 2 — CPF
        if attempts < 2:
            if cpf is None:
                return "SOLICITAR_CPF: Pra eu te ajudar mais rápido, me passa seu CPF (só números, por favor)?"
            normalized = _normalize_cpf(cpf)
            if normalized:
                student = await self._cademi.get_student_by_cpf(normalized)
                if student:
                    await self._repo.update_status(
                        case_id=case.id,
                        status="REACTIVE_LINK_SENT",
                        search_attempts=2,
                    )
                    log.info("cademi_found_cpf", account_id=account_id)
                    return f"ENCONTRADO: {student.name} (cpf). student_id={student.id}"

        # Tentativa 3 — nome + telefone
        if attempts < CADEMI_MAX_ATTEMPTS:
            try:
                student = await self._cademi.get_student_by_name_phone(
                    name=student_name or "", phone=phone
                )
            except NotImplementedError:
                student = None
            if student:
                await self._repo.update_status(
                    case_id=case.id,
                    status="REACTIVE_LINK_SENT",
                    search_attempts=CADEMI_MAX_ATTEMPTS,
                )
                return f"ENCONTRADO: {student.name} (nome+telefone). student_id={student.id}"

        await self._repo.update_status(
            case_id=case.id,
            status="REACTIVE_ESCALATED",
            search_attempts=CADEMI_MAX_ATTEMPTS,
        )
        log.warning("cademi_exhausted", account_id=account_id)
        return "ESCALADO: Aluno não localizado após 3 tentativas. Transferindo para humano."
