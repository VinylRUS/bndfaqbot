from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from database.models.role import RoleEnum
from database.models.ticket import TicketStatus
from database.repositories.user_repo import UserRepository
from database.repositories.ticket_repo import TicketRepository
from database.repositories.rating_repo import RatingRepository


class StatisticsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.user_repo = UserRepository(session)
        self.ticket_repo = TicketRepository(session)
        self.rating_repo = RatingRepository(session)

    async def get_statistics(self) -> dict:
        total_users = await self.user_repo.count()
        total_operators = await self.user_repo.count_by_role(RoleEnum.OPERATOR)
        total_tickets = await self.ticket_repo.count_all()
        open_tickets = (
            await self.ticket_repo.count_by_status(TicketStatus.NEW)
            + await self.ticket_repo.count_by_status(TicketStatus.IN_PROGRESS)
        )
        closed_tickets = await self.ticket_repo.count_by_status(TicketStatus.CLOSED)
        avg_score = await self.rating_repo.get_average_score()
        by_category = await self.ticket_repo.count_by_category()

        return {
            "total_users": total_users,
            "total_operators": total_operators,
            "total_tickets": total_tickets,
            "open_tickets": open_tickets,
            "closed_tickets": closed_tickets,
            "average_score": round(avg_score, 2) if avg_score else 0.0,
            "by_category": by_category,
        }
