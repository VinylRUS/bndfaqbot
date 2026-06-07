from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.rating import Rating
from app.database.repositories.rating_repo import RatingRepository


class RatingService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.rating_repo = RatingRepository(session)

    async def create(self, ticket_id: int, user_id: int, score: int) -> Rating:
        return await self.rating_repo.create(
            ticket_id=ticket_id, user_id=user_id, score=score
        )

    async def get_by_ticket(self, ticket_id: int) -> Optional[Rating]:
        return await self.rating_repo.get_by_ticket(ticket_id)

    async def get_average_score(self) -> Optional[float]:
        return await self.rating_repo.get_average_score()

    async def get_average_by_operator(self, operator_id: int) -> Optional[float]:
        return await self.rating_repo.get_average_by_operator(operator_id)

    async def has_rated(self, ticket_id: int) -> bool:
        rating = await self.rating_repo.get_by_ticket(ticket_id)
        return rating is not None
