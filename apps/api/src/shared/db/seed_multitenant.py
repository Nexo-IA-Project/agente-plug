from __future__ import annotations

import asyncio
from uuid import UUID

from sqlalchemy import text

from shared.adapters.db.session import session_scope
from shared.adapters.kb.jwt_handler import hash_password

SEED_ACCOUNT_ID = UUID("00000000-0000-0000-0000-0000000000aa")
SEED_OWNER_EMAIL = "owner@seed.local"
SEED_OWNER_PASSWORD = "seed-owner-pass"
SEED_IDENTITY_ID = "00000000-0000-0000-0000-0000000000bb"
SEED_MEMBERSHIP_ID = "00000000-0000-0000-0000-0000000000cc"


async def run() -> None:
    pw_hash = hash_password(SEED_OWNER_PASSWORD)
    async with session_scope() as s:
        await s.execute(
            text(
                "INSERT INTO accounts (id, name, settings, created_at, legal_name) "
                "VALUES (:id, 'Seed Co', '{}'::jsonb, NOW(), 'Seed Co LTDA') "
                "ON CONFLICT (id) DO NOTHING"
            ),
            {"id": str(SEED_ACCOUNT_ID)},
        )
        await s.execute(
            text(
                "INSERT INTO identities (id, email, password_hash, name, must_change_password, is_active, created_at) "
                "VALUES (:id, :email, :pw, 'Seed Owner', FALSE, TRUE, NOW()) "
                "ON CONFLICT (email) DO NOTHING"
            ),
            {"id": SEED_IDENTITY_ID, "email": SEED_OWNER_EMAIL, "pw": pw_hash},
        )
        await s.execute(
            text(
                "INSERT INTO memberships (id, identity_id, account_id, role, is_owner, is_active, created_at) "
                "VALUES (:id, :iid, :acc, 'admin', TRUE, TRUE, NOW()) "
                "ON CONFLICT (identity_id, account_id) DO NOTHING"
            ),
            {"id": SEED_MEMBERSHIP_ID, "iid": SEED_IDENTITY_ID, "acc": str(SEED_ACCOUNT_ID)},
        )
    print(f"Seed OK: {SEED_OWNER_EMAIL} / {SEED_OWNER_PASSWORD} (account {SEED_ACCOUNT_ID})")


if __name__ == "__main__":
    asyncio.run(run())
