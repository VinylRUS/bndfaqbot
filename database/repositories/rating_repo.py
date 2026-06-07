from __future__ import annotations

from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.rating import Rating


class RatingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, ticket_id: int, user_id: int, score: int) -> Rating:
        rating = Rating(ticket_id=ticket_id, user_id=user_id, score=score)
        self.session.add(rating)
        await self.session.flush()
        return rating

    async def get_by_ticket(self, ticket_id: int) -> Optional[Rating]:
        result = await self.session.execute(
            select(Rating).where(Rating.ticket_id == ticket_id)
        )
        return result.scalar_one_or_none()

    async def get_average_score(self) -> Optional[float]:
        result = await self.session.execute(select(func.avg(Rating.score)))
        return result.scalar_one_or_none()

    async def get_average_by_operator(self, operator_id: int) -> Optional[float]:
        from database.models.ticket import Ticket
        result = await self.session.execute(
            select(func.avg(Rating.score))
            .join(Ticket, Rating.ticket_id == Ticket.id)
            .where(Ticket.operator_id == operator_id)
        )
        return result.scalar_one_or_none()
