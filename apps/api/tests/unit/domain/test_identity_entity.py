from __future__ import annotations

from shared.domain.entities.identity import Identity


def test_identity_defaults():
    ident = Identity(email="a@x.com", password_hash="h", name="Alice")
    assert ident.must_change_password is True
    assert ident.is_active is True
    assert ident.avatar is None
    assert isinstance(ident.id, str) and len(ident.id) == 36
    assert ident.last_login_at is None
