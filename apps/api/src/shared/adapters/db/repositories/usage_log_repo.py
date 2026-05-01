from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.adapters.db.models import KbUsageLogModel


class UsageLogRepository:
    """Session lifecycle managed by caller. Uses flush(), not commit()."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record_no_result(self, account_id: int, query: str) -> None:
        log = KbUsageLogModel(
            account_id=account_id,
            query=query,
            result_count=0,
        )
        self._session.add(log)
        await self._session.flush()

    async def list_recent(self, account_id: int, limit: int = 50) -> list[dict]:
        result = await self._session.execute(
            select(KbUsageLogModel)
            .where(KbUsageLogModel.account_id == account_id)
            .order_by(KbUsageLogModel.created_at.desc())
            .limit(limit)
        )
        return [
            {
                "id": m.id,
                "account_id": m.account_id,
                "query": m.query,
                "result_count": m.result_count,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in result.scalars().all()
        ]
