from __future__ import annotations

from typing import Optional

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.quick_reply import QuickReply


class QuickReplyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, reply_id: int) -> Optional[QuickReply]:
        result = await self.session.execute(select(QuickReply).where(QuickReply.id == reply_id))
        return result.scalar_one_or_none()

    async def get_by_user(self, user_id: int) -> list[QuickReply]:
        result = await self.session.execute(
            select(QuickReply)
            .where(QuickReply.user_id == user_id)
            .order_by(QuickReply.name)
        )
        return list(result.scalars().all())

    async def create(self, user_id: int, name: str, text: str) -> QuickReply:
        reply = QuickReply(user_id=user_id, name=name, text=text)
        self.session.add(reply)
        await self.session.flush()
        return reply

    async def delete(self, reply_id: int) -> bool:
        reply = await self.get_by_id(reply_id)
        if reply:
            await self.session.delete(reply)
            await self.session.flush()
            return True
        return False

    async def count_by_user(self, user_id: int) -> int:
        from sqlalchemy import func
        result = await self.session.execute(
            select(func.count(QuickReply.id)).where(QuickReply.user_id == user_id)
        )
        return result.scalar_one()
