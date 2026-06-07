from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from database.models.auto_answer import AutoAnswer
from database.repositories.auto_answer_repo import AutoAnswerRepository
from database.repositories.audit_log_repo import AuditLogRepository
from utils.text_matcher import find_matching_auto_answer


class AutoAnswerService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.auto_answer_repo = AutoAnswerRepository(session)
        self.audit_repo = AuditLogRepository(session)

    async def find_match(self, text: str) -> Optional[AutoAnswer]:
        active_answers = await self.auto_answer_repo.get_all_active()
        return find_matching_auto_answer(text, active_answers)

    async def get_all(self) -> list[AutoAnswer]:
        return await self.auto_answer_repo.get_all()

    async def get_by_id(self, auto_answer_id: int) -> Optional[AutoAnswer]:
        return await self.auto_answer_repo.get_by_id(auto_answer_id)

    async def create(self, admin_id: int, keywords: str, answer: str) -> AutoAnswer:
        auto_answer = await self.auto_answer_repo.create(keywords=keywords, answer=answer)
        await self.audit_repo.create(
            user_id=admin_id,
            role="admin",
            action="create_auto_answer",
            object_type="auto_answer",
            object_id=auto_answer.id,
        )
        return auto_answer

    async def update(
        self,
        admin_id: int,
        auto_answer_id: int,
        keywords: Optional[str] = None,
        answer: Optional[str] = None,
    ) -> Optional[AutoAnswer]:
        auto_answer = await self.auto_answer_repo.update(
            auto_answer_id, keywords=keywords, answer=answer
        )
        if auto_answer:
            await self.audit_repo.create(
                user_id=admin_id,
                role="admin",
                action="update_auto_answer",
                object_type="auto_answer",
                object_id=auto_answer_id,
            )
        return auto_answer

    async def toggle_active(self, admin_id: int, auto_answer_id: int) -> Optional[AutoAnswer]:
        auto_answer = await self.auto_answer_repo.toggle_active(auto_answer_id)
        if auto_answer:
            await self.audit_repo.create(
                user_id=admin_id,
                role="admin",
                action="toggle_auto_answer",
                object_type="auto_answer",
                object_id=auto_answer_id,
                details=f"is_active={auto_answer.is_active}",
            )
        return auto_answer

    async def delete(self, admin_id: int, auto_answer_id: int) -> bool:
        result = await self.auto_answer_repo.delete(auto_answer_id)
        if result:
            await self.audit_repo.create(
                user_id=admin_id,
                role="admin",
                action="delete_auto_answer",
                object_type="auto_answer",
                object_id=auto_answer_id,
            )
        return result
