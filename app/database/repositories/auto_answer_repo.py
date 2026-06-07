from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.auto_answer import AutoAnswer


class AutoAnswerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, auto_answer_id: int) -> Optional[AutoAnswer]:
        result = await self.session.execute(
            select(AutoAnswer).where(AutoAnswer.id == auto_answer_id)
        )
        return result.scalar_one_or_none()

    async def get_all_active(self) -> list[AutoAnswer]:
        result = await self.session.execute(
            select(AutoAnswer).where(AutoAnswer.is_active.is_(True))
        )
        return list(result.scalars().all())

    async def get_all(self) -> list[AutoAnswer]:
        result = await self.session.execute(select(AutoAnswer))
        return list(result.scalars().all())

    async def create(self, keywords: str, answer: str) -> AutoAnswer:
        auto_answer = AutoAnswer(keywords=keywords, answer=answer, is_active=True)
        self.session.add(auto_answer)
        await self.session.flush()
        return auto_answer

    async def update(
        self,
        auto_answer_id: int,
        keywords: Optional[str] = None,
        answer: Optional[str] = None,
    ) -> Optional[AutoAnswer]:
        auto_answer = await self.get_by_id(auto_answer_id)
        if auto_answer:
            if keywords is not None:
                auto_answer.keywords = keywords
            if answer is not None:
                auto_answer.answer = answer
            await self.session.flush()
        return auto_answer

    async def toggle_active(self, auto_answer_id: int) -> Optional[AutoAnswer]:
        auto_answer = await self.get_by_id(auto_answer_id)
        if auto_answer:
            auto_answer.is_active = not auto_answer.is_active
            await self.session.flush()
        return auto_answer

    async def delete(self, auto_answer_id: int) -> bool:
        auto_answer = await self.get_by_id(auto_answer_id)
        if auto_answer:
            await self.session.delete(auto_answer)
            await self.session.flush()
            return True
        return False
