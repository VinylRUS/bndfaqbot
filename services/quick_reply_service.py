from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from database.models.quick_reply import QuickReply
from database.repositories.quick_reply_repo import QuickReplyRepository


class QuickReplyService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = QuickReplyRepository(session)

    async def get_user_replies(self, user_id: int) -> list[QuickReply]:
        return await self.repo.get_by_user(user_id)

    async def create(self, user_id: int, name: str, text: str) -> QuickReply:
        # Auto-generate name from text if empty
        if not name or not name.strip():
            name = text.strip()[:30] + ("..." if len(text.strip()) > 30 else "")
        return await self.repo.create(user_id=user_id, name=name.strip(), text=text.strip())

    async def delete(self, reply_id: int) -> bool:
        return await self.repo.delete(reply_id)

    async def get_by_id(self, reply_id: int) -> QuickReply | None:
        return await self.repo.get_by_id(reply_id)
