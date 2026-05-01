from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from cryptography.fernet import Fernet


@dataclass
class CredentialsCipher:
    key: str

    def __post_init__(self) -> None:
        self._fernet = Fernet(self.key.encode())

    def encrypt(self, payload: dict[str, Any]) -> bytes:
        return self._fernet.encrypt(json.dumps(payload).encode())

    def decrypt(self, token: bytes) -> dict[str, Any]:
        return json.loads(self._fernet.decrypt(token).decode())
