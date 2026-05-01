from __future__ import annotations

import re
from dataclasses import dataclass

from nexoia.domain.errors import InvalidPhoneError

_NON_DIGITS = re.compile(r"\D")
_BR_COUNTRY_CODE = "55"


@dataclass(frozen=True, slots=True)
class Phone:
    e164: str

    @classmethod
    def parse(cls, raw: str) -> Phone:
        digits = _NON_DIGITS.sub("", raw)
        if not digits.isdigit() or len(digits) < 10:
            raise InvalidPhoneError(f"Invalid phone: {raw!r}")
        if not digits.startswith(_BR_COUNTRY_CODE):
            digits = _BR_COUNTRY_CODE + digits
        if len(digits) < 12 or len(digits) > 13:
            raise InvalidPhoneError(f"Invalid phone after normalization: {digits!r}")
        return cls(e164=f"+{digits}")

    def __str__(self) -> str:
        return self.e164
