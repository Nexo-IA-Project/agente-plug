from __future__ import annotations

from shared.adapters.kb.jwt_handler import create_access_token, verify_token


def test_token_roundtrips_membership_claims():
    token = create_access_token(
        data={
            "sub": "a@x.com",
            "identity_id": "id-1",
            "account_id": "acc-uuid",
            "membership_id": "m-1",
            "role": "admin",
        },
        secret="s",
        expire_minutes=10,
    )
    payload = verify_token(token, secret="s")
    assert payload["identity_id"] == "id-1"
    assert payload["membership_id"] == "m-1"
    assert payload["account_id"] == "acc-uuid"
