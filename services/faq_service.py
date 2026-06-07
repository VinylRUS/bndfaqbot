from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from database.models.faq import FAQ
from database.repositories.faq_repo import FAQRepository
from database.repositories.audit_log_repo import AuditLogRepository


class FAQService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.faq_repo = FAQRepository(session)
        self.audit_repo = AuditLogRepository(session)

    async def get_all_active(self) -> list[FAQ]:
        return await self.faq_repo.get_all_active()

    async def get_all(self) -> list[FAQ]:
        return await self.faq_repo.get_all()

    async def get_by_id(self, faq_id: int) -> Optional[FAQ]:
        return await self.faq_repo.get_by_id(faq_id)

    async def create(self, admin_id: int, question: str, answer: str) -> FAQ:
        faq = await self.faq_repo.create(question=question, answer=answer)
        await self.audit_repo.create(
            user_id=admin_id,
            role="admin",
            action="create_faq",
            object_type="faq",
            object_id=faq.id,
            details=f"Created FAQ: {question[:50]}",
        )
        return faq

    async def update(
        self,
        admin_id: int,
        faq_id: int,
        question: Optional[str] = None,
        answer: Optional[str] = None,
    ) -> Optional[FAQ]:
        faq = await self.faq_repo.update(faq_id, question=question, answer=answer)
        if faq:
            await self.audit_repo.create(
                user_id=admin_id,
                role="admin",
                action="update_faq",
                object_type="faq",
                object_id=faq_id,
            )
        return faq

    async def toggle_active(self, admin_id: int, faq_id: int) -> Optional[FAQ]:
        faq = await self.faq_repo.toggle_active(faq_id)
        if faq:
            await self.audit_repo.create(
                user_id=admin_id,
                role="admin",
                action="toggle_faq",
                object_type="faq",
                object_id=faq_id,
                details=f"FAQ is_active={faq.is_active}",
            )
        return faq

    async def delete(self, admin_id: int, faq_id: int) -> bool:
        result = await self.faq_repo.delete(faq_id)
        if result:
            await self.audit_repo.create(
                user_id=admin_id,
                role="admin",
                action="delete_faq",
                object_type="faq",
                object_id=faq_id,
            )
        return result
