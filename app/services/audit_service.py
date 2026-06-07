from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.audit_log import AuditLog
from app.database.repositories.audit_log_repo import AuditLogRepository


class AuditService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.audit_repo = AuditLogRepository(session)

    async def log(
        self,
        user_id: Optional[int],
        role: Optional[str],
        action: str,
        object_type: Optional[str] = None,
        object_id: Optional[int] = None,
        details: Optional[str] = None,
    ) -> AuditLog:
        return await self.audit_repo.create(
            user_id=user_id,
            role=role,
            action=action,
            object_type=object_type,
            object_id=object_id,
            details=details,
        )

    async def log_unauthorized_access(self, user_id: Optional[int], role: Optional[str], action: str) -> AuditLog:
        return await self.audit_repo.create(
            user_id=user_id,
            role=role,
            action="unauthorized_access",
            object_type="security",
            details=f"Attempted action: {action}",
        )

    async def get_recent_logs(self, limit: int = 100) -> list[AuditLog]:
        return await self.audit_repo.get_all(limit=limit)

    async def get_user_logs(self, user_id: int, limit: int = 50) -> list[AuditLog]:
        return await self.audit_repo.get_by_user(user_id, limit=limit)
