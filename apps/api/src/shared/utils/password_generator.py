from __future__ import annotations

import secrets
import string

_SYMBOLS = "!@#$%^&*+="
_ALPHABET = string.ascii_letters + string.digits + _SYMBOLS


def generate_temp_password(length: int = 16) -> str:
    """Generate a cryptographically secure random password.

    Guarantees at least one letter, one digit, and one symbol.
    """
    while True:
        pwd = "".join(secrets.choice(_ALPHABET) for _ in range(length))
        if (
            any(c.isalpha() for c in pwd)
            and any(c.isdigit() for c in pwd)
            and any(c in _SYMBOLS for c in pwd)
        ):
            return pwd
