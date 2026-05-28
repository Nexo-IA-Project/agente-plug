from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from shared.domain.entities.user import User, UserRole


def test_user_role_values():
    assert UserRole.ADMIN.value == "admin"
    assert UserRole.OPERATOR.value == "operator"


def test_user_creation_with_defaults():
    user = User(
        account_id=1,
        name="Fabio Dias",
        email="fabio@example.com",
        password_hash="$2b$12$abc",
        role=UserRole.ADMIN,
    )
    assert isinstance(user.id, str)
    assert user.must_change_password is True
    assert user.is_active is True
    assert user.avatar is None
    assert user.last_login_at is None
    assert isinstance(user.created_at, datetime)


def test_user_with_all_fields():
    uid = str(uuid4())
    now = datetime.now(UTC)
    user = User(
        id=uid,
        account_id=2,
        name="Joana",
        email="joana@example.com",
        password_hash="hash",
        role=UserRole.OPERATOR,
        avatar=b"\xff\xd8\xff",
        must_change_password=False,
        is_active=True,
        created_at=now,
        last_login_at=now,
    )
    assert user.id == uid
    assert user.role == UserRole.OPERATOR
    assert user.avatar == b"\xff\xd8\xff"
