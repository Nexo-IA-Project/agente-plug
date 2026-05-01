# tests/unit/infrastructure/kb/test_jwt_handler.py
from datetime import UTC, datetime

import pytest

from shared.adapters.kb.jwt_handler import (
    create_access_token,
    hash_password,
    verify_password,
    verify_token,
)


def test_hash_and_verify_password():
    hashed = hash_password("mysecret")
    assert hashed != "mysecret"
    assert verify_password("mysecret", hashed) is True
    assert verify_password("wrong", hashed) is False


def test_create_and_verify_token():
    data = {"sub": "user@example.com", "account_id": 1, "role": "admin"}
    token = create_access_token(data, secret="test-secret", expire_minutes=60)
    assert isinstance(token, str)
    payload = verify_token(token, secret="test-secret")
    assert payload["sub"] == "user@example.com"
    assert payload["account_id"] == 1
    assert payload["role"] == "admin"
    assert "exp" in payload


def test_verify_token_wrong_secret_raises():
    from jose import JWTError
    data = {"sub": "user@example.com"}
    token = create_access_token(data, secret="correct-secret", expire_minutes=10)
    with pytest.raises(JWTError):
        verify_token(token, secret="wrong-secret")


def test_token_expiry_is_in_future():
    data = {"sub": "user@example.com"}
    token = create_access_token(data, secret="s", expire_minutes=30)
    payload = verify_token(token, secret="s")
    exp = datetime.fromtimestamp(payload["exp"], tz=UTC)
    assert exp > datetime.now(UTC)
