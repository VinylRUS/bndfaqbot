from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.audit_log import AuditLog


class AuditLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        user_id: Optional[int],
        role: Optional[str],
        action: str,
        object_type: Optional[str] = None,
        object_id: Optional[int] = None,
        details: Optional[str] = None,
    ) -> AuditLog:
        log = AuditLog(
            user_id=user_id,
            role=role,
            action=action,
            object_type=object_type,
            object_id=object_id,
            details=details,
        )
        self.session.add(log)
        await self.session.flush()
        return log

    async def get_all(self, limit: int = 100) -> list[AuditLog]:
        result = await self.session.execute(
            select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_user(self, user_id: int, limit: int = 50) -> list[AuditLog]:
        result = await self.session.execute(
            select(AuditLog)
            .where(AuditLog.user_id == user_id)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
