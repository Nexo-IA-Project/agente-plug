from __future__ import annotations

from uuid import UUID, uuid4

from shared.domain.entities.membership import Membership
from shared.domain.entities.user import UserRole


def test_membership_defaults():
    acc = uuid4()
    ident_id = str(uuid4())
    m = Membership(identity_id=ident_id, account_id=acc, role=UserRole.OPERATOR)
    assert m.is_owner is False
    assert m.is_active is True
    assert m.profile_id is None
    assert isinstance(UUID(m.id), UUID)
