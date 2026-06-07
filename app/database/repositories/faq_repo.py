from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.faq import FAQ


class FAQRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, faq_id: int) -> Optional[FAQ]:
        result = await self.session.execute(select(FAQ).where(FAQ.id == faq_id))
        return result.scalar_one_or_none()

    async def get_all_active(self) -> list[FAQ]:
        result = await self.session.execute(
            select(FAQ).where(FAQ.is_active.is_(True))
        )
        return list(result.scalars().all())

    async def get_all(self) -> list[FAQ]:
        result = await self.session.execute(select(FAQ))
        return list(result.scalars().all())

    async def create(self, question: str, answer: str) -> FAQ:
        faq = FAQ(question=question, answer=answer, is_active=True)
        self.session.add(faq)
        await self.session.flush()
        return faq

    async def update(self, faq_id: int, question: Optional[str] = None, answer: Optional[str] = None) -> Optional[FAQ]:
        faq = await self.get_by_id(faq_id)
        if faq:
            if question is not None:
                faq.question = question
            if answer is not None:
                faq.answer = answer
            await self.session.flush()
        return faq

    async def toggle_active(self, faq_id: int) -> Optional[FAQ]:
        faq = await self.get_by_id(faq_id)
        if faq:
            faq.is_active = not faq.is_active
            await self.session.flush()
        return faq

    async def delete(self, faq_id: int) -> bool:
        faq = await self.get_by_id(faq_id)
        if faq:
            await self.session.delete(faq)
            await self.session.flush()
            return True
        return False
