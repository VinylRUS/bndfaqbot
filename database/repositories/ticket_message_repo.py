from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.ticket_message import TicketMessage


class TicketMessageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        ticket_id: int,
        sender_id: int,
        text: str,
        file_id: str | None = None,
        file_type: str | None = None,
    ) -> TicketMessage:
        message = TicketMessage(
            ticket_id=ticket_id,
            sender_id=sender_id,
            text=text,
            file_id=file_id,
            file_type=file_type,
        )
        self.session.add(message)
        await self.session.flush()
        return message

    async def get_by_ticket(self, ticket_id: int) -> list[TicketMessage]:
        result = await self.session.execute(
            select(TicketMessage)
            .where(TicketMessage.ticket_id == ticket_id)
            .order_by(TicketMessage.created_at.asc())
        )
        return list(result.scalars().all())
