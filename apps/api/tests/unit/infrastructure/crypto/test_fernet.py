import pytest
from cryptography.fernet import Fernet

from shared.adapters.crypto.fernet import CredentialsCipher


def test_encrypt_decrypt_roundtrip() -> None:
    key = Fernet.generate_key().decode()
    cipher = CredentialsCipher(key=key)
    payload = {"token": "abc", "secret": "xyz"}
    token = cipher.encrypt(payload)
    assert isinstance(token, bytes)
    assert cipher.decrypt(token) == payload


def test_decrypt_with_different_key_fails() -> None:
    cipher1 = CredentialsCipher(key=Fernet.generate_key().decode())
    cipher2 = CredentialsCipher(key=Fernet.generate_key().decode())
    token = cipher1.encrypt({"x": 1})
    with pytest.raises((Exception,)):
        cipher2.decrypt(token)
