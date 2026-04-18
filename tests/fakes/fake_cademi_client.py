from nexoia.domain.errors import CademiError
from nexoia.domain.ports.cademi_port import CademiStudent


class FakeCademiClient:
    """Fake configurável para testes. `fail_times` simula falhas consecutivas."""

    def __init__(
        self,
        student: CademiStudent | None = None,
        fail_times: int = 0,
        access_link: str = "https://cademi.com.br/auto-login/test-token",
    ) -> None:
        self._student = student
        self._fail_times = fail_times
        self._access_link = access_link
        self.call_count = 0

    async def get_student_by_email(self, email: str) -> CademiStudent | None:
        self.call_count += 1
        if self.call_count <= self._fail_times:
            raise CademiError(f"Connection failed (attempt {self.call_count})")
        return self._student

    async def get_student_by_cpf(self, cpf: str) -> CademiStudent | None:
        return self._student

    async def get_access_link(self, student_id: str, product_id: str) -> str:
        return self._access_link
