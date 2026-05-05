from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from shared.adapters.db.models import ApiTokenModel


def generate_token() -> str:
    """Generates a raw token: nxia_<64 hex chars>. Show only on creation."""
    return "nxia_" + secrets.token_hex(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@dataclass
class ApiTokenRepository:
    session: AsyncSession

    async def create(self, *, name: str) -> tuple[ApiTokenModel, str]:
        """Creates a token. Returns (model, raw_token). raw_token is not stored."""
        raw = generate_token()
        model = ApiTokenModel(
            id=uuid.uuid4(),
            name=name,
            token_hash=hash_token(raw),
        )
        self.session.add(model)
        await self.session.flush()
        return model, raw

    async def validate(self, *, raw_token: str) -> bool:
        """Returns True if token exists and is active."""
        h = hash_token(raw_token)
        result = await self.session.execute(
            select(ApiTokenModel).where(
                ApiTokenModel.token_hash == h,
                ApiTokenModel.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none() is not None

    async def touch(self, *, raw_token: str) -> None:
        """Updates last_used_at. Call in background after validation."""
        h = hash_token(raw_token)
        await self.session.execute(
            update(ApiTokenModel)
            .where(ApiTokenModel.token_hash == h)
            .values(last_used_at=datetime.now(UTC))
        )

    async def list_all(self) -> list[ApiTokenModel]:
        result = await self.session.execute(
            select(ApiTokenModel).order_by(ApiTokenModel.created_at.desc())
        )
        return list(result.scalars().all())

    async def revoke(self, *, token_id: uuid.UUID) -> bool:
        """Deactivates token. Returns False if not found."""
        result = await self.session.execute(
            select(ApiTokenModel).where(ApiTokenModel.id == token_id)
        )
        model = result.scalar_one_or_none()
        if model is None:
            return False
        model.is_active = False
        return True
