# tests/fakes/fake_cademi_client.py
from __future__ import annotations

from shared.domain.errors import CademiError
from shared.domain.ports.cademi_port import CademiStudent


class FakeCademiClient:
    """
    Fake configurável para testes da Capability Welcome (spec ②) e Access (spec ③).

    Modos de uso:
    1) Compat spec ②: passe `student=...` — todos métodos retornam o mesmo aluno.
    2) Cascade spec ③: passe `students_by_email`, `students_by_cpf`, `students_by_name_phone`.
    3) Falhas: `fail_times=N` faz os primeiros N chamadas de get_student_by_email levantarem CademiError.
    4) Stub nome+telefone (CQ-A02): por padrão levanta NotImplementedError.
    """

    def __init__(
        self,
        *,
        student: CademiStudent | None = None,
        students_by_email: dict[str, CademiStudent] | None = None,
        students_by_cpf: dict[str, CademiStudent] | None = None,
        students_by_name_phone: dict[tuple[str, str], CademiStudent] | None = None,
        name_phone_supported: bool = False,
        fail_times: int = 0,
        access_link: str = "https://cademi.com.br/auto-login/test-token",
    ) -> None:
        self._student = student
        self._students_by_email = students_by_email or {}
        self._students_by_cpf = students_by_cpf or {}
        self._students_by_name_phone = students_by_name_phone or {}
        self._name_phone_supported = name_phone_supported
        self._fail_times = fail_times
        self._access_link = access_link
        self.call_count = 0
        self.email_calls = 0
        self.cpf_calls = 0
        self.name_phone_calls = 0

    async def get_student_by_email(self, email: str) -> CademiStudent | None:
        self.call_count += 1
        self.email_calls += 1
        if self.call_count <= self._fail_times:
            raise CademiError(f"Connection failed (attempt {self.call_count})")
        if self._students_by_email:
            return self._students_by_email.get(email)
        return self._student

    async def get_student_by_cpf(self, cpf: str) -> CademiStudent | None:
        self.cpf_calls += 1
        if self._students_by_cpf:
            return self._students_by_cpf.get(cpf)
        return self._student

    async def get_student_by_name_phone(
        self, name: str, phone: str
    ) -> CademiStudent | None:
        self.name_phone_calls += 1
        if not self._name_phone_supported:
            raise NotImplementedError(
                "FakeCademiClient.get_student_by_name_phone não habilitado — "
                "ver OPEN_QUESTIONS.md#CQ-A02"
            )
        return self._students_by_name_phone.get((name, phone))

    async def get_access_link(self, student_id: str, product_id: str) -> str:
        return self._access_link
