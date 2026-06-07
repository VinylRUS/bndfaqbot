from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.category import Category


class CategoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, category_id: int) -> Optional[Category]:
        result = await self.session.execute(
            select(Category).where(Category.id == category_id)
        )
        return result.scalar_one_or_none()

    async def get_roots(self) -> list[Category]:
        result = await self.session.execute(
            select(Category).where(Category.parent_id.is_(None))
        )
        return list(result.scalars().all())

    async def get_topics(self, parent_id: int) -> list[Category]:
        result = await self.session.execute(
            select(Category).where(Category.parent_id == parent_id)
        )
        return list(result.scalars().all())

    async def get_all(self) -> list[Category]:
        result = await self.session.execute(select(Category))
        return list(result.scalars().all())

    async def create(
        self,
        name: str,
        emoji: str = "",
        parent_id: Optional[int] = None,
    ) -> Category:
        category = Category(name=name, emoji=emoji, parent_id=parent_id)
        self.session.add(category)
        await self.session.flush()
        return category

    async def seed_defaults(self) -> None:
        existing = await self.get_roots()
        if existing:
            return

        finance = await self.create(name="Финансы", emoji="💰")
        for topic in ["зарплата", "аванс", "расчётный лист", "удержания", "выплаты"]:
            await self.create(name=topic, parent_id=finance.id)

        vacation = await self.create(name="Отпуска", emoji="🏖")
        for topic in ["отпуск", "больничный", "отгулы", "график отпусков"]:
            await self.create(name=topic, parent_id=vacation.id)

        await self.create(name="Прочее", emoji="📦")
