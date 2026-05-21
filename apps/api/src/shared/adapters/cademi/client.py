from __future__ import annotations

from typing import TYPE_CHECKING

from shared.domain.ports.cademi_port import CademiStudent

if TYPE_CHECKING:
    from shared.domain.entities.account_config import AccountConfig


class CademiClient:
    def __init__(self, base_url: str, api_key: str) -> None:
        self._base_url = base_url
        self._api_key = api_key

    @classmethod
    def from_account_config(cls, config: AccountConfig) -> CademiClient:
        return cls(
            base_url=config.integration.cademi_api_url,
            api_key=config.integration.cademi_api_key,
        )

    async def get_student_by_email(self, email: str) -> CademiStudent | None:
        raise NotImplementedError("CademiClient não implementado — ver OPEN_QUESTIONS.md#CQ-W01")

    async def get_student_by_cpf(self, cpf: str) -> CademiStudent | None:
        raise NotImplementedError("CademiClient não implementado — ver OPEN_QUESTIONS.md#CQ-W01")

    async def get_student_by_name_phone(self, name: str, phone: str) -> CademiStudent | None:
        raise NotImplementedError("CademiClient não implementado — ver OPEN_QUESTIONS.md#CQ-W01")

    async def get_access_link(self, student_id: str, product_id: str) -> str:
        raise NotImplementedError("CademiClient não implementado — ver OPEN_QUESTIONS.md#CQ-W01")
