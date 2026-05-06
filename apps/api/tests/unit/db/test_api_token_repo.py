from __future__ import annotations

import hashlib

from shared.adapters.db.repositories.api_token_repo import generate_token, hash_token


def test_generate_token_has_nxia_prefix():
    token = generate_token()
    assert token.startswith("nxia_")
    assert len(token) > 10


def test_generate_token_is_unique():
    assert generate_token() != generate_token()


def test_hash_token_is_sha256():
    token = "nxia_abc"
    expected = hashlib.sha256(token.encode()).hexdigest()
    assert hash_token(token) == expected
    assert len(hash_token(token)) == 64


def test_hash_token_is_deterministic():
    token = "nxia_test"
    assert hash_token(token) == hash_token(token)
