from __future__ import annotations

import re
from dataclasses import dataclass

from shared.domain.errors import InvalidPhoneError

_NON_DIGITS = re.compile(r"\D")
_BR_COUNTRY_CODE = "55"


@dataclass(frozen=True, slots=True)
class Phone:
    """Telefone normalizado em formato E.164 (`+5511984479440`).

    Aceita variações comuns vindas de gateways (Hubla, Stripe etc.):

    | Input cru                  | Resultado normalizado |
    |----------------------------|-----------------------|
    | `+5511984479440`           | `+5511984479440`      |
    | `5511984479440`            | `+5511984479440`      |
    | `11984479440`              | `+5511984479440`      |
    | `(11) 98447-9440`          | `+5511984479440`      |
    | `+55 11 9 8447-9440`       | `+5511984479440`      |
    | `1184479440` (fixo SP)     | `+551184479440`       |
    | `551184479440` (fixo c/55) | `+551184479440`       |

    Sempre raise `InvalidPhoneError` quando:
    - String vazia / None / só espaços
    - Sem nenhum dígito após limpeza
    - Quantidade de dígitos fora de 10-13
    - 12-13 dígitos sem prefixo `55`
    - DDD inválido (fora de 11-99)
    """

    e164: str

    @classmethod
    def parse(cls, raw: str | None) -> Phone:
        if raw is None or not str(raw).strip():
            raise InvalidPhoneError("phone is required")

        digits = _NON_DIGITS.sub("", str(raw))
        if not digits:
            raise InvalidPhoneError(f"phone has no digits: {raw!r}")

        # Sem código de país (10=fixo, 11=celular com 9): prefixa 55
        if len(digits) in (10, 11):
            digits = _BR_COUNTRY_CODE + digits
        # Com código de país BR
        elif len(digits) in (12, 13):
            if not digits.startswith(_BR_COUNTRY_CODE):
                raise InvalidPhoneError(
                    f"phone with {len(digits)} digits must start with country code 55: {raw!r}"
                )
        else:
            raise InvalidPhoneError(f"phone must have 10-13 digits (got {len(digits)}): {raw!r}")

        # Valida DDD (11-99 — DDDs no Brasil começam em 11)
        ddd = int(digits[2:4])
        if not (11 <= ddd <= 99):
            raise InvalidPhoneError(f"invalid DDD {ddd:02d}: {raw!r}")

        return cls(e164=f"+{digits}")

    def __str__(self) -> str:
        return self.e164
