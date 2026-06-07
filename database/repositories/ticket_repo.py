from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.models.ticket import Ticket, TicketStatus


class TicketRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, ticket_id: int) -> Optional[Ticket]:
        result = await self.session.execute(select(Ticket).where(Ticket.id == ticket_id))
        return result.scalar_one_or_none()

    async def get_by_id_with_details(self, ticket_id: int) -> Optional[Ticket]:
        """Load ticket with category and rating only (for display)."""
        stmt = (
            select(Ticket)
            .where(Ticket.id == ticket_id)
            .options(
                selectinload(Ticket.category),
                selectinload(Ticket.rating),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id_full(self, ticket_id: int) -> Optional[Ticket]:
        """Load ticket with all details for detail view."""
        stmt = (
            select(Ticket)
            .where(Ticket.id == ticket_id)
            .options(
                selectinload(Ticket.author),
                selectinload(Ticket.operator),
                selectinload(Ticket.category),
                selectinload(Ticket.rating),
                selectinload(Ticket.messages),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_number(self, number: int) -> Optional[Ticket]:
        result = await self.session.execute(
            select(Ticket).where(Ticket.number == number)
        )
        return result.scalar_one_or_none()

    async def get_next_number(self) -> int:
        result = await self.session.execute(select(func.coalesce(func.max(Ticket.number), 0)))
        return result.scalar_one() + 1

    async def create(
        self,
        author_id: int,
        category_id: int,
        text: str,
    ) -> Ticket:
        number = await self.get_next_number()
        ticket = Ticket(
            number=number,
            author_id=author_id,
            category_id=category_id,
            text=text,
            status=TicketStatus.NEW,
        )
        self.session.add(ticket)
        await self.session.flush()
        return ticket

    async def get_user_tickets(self, author_id: int, limit: int = 50) -> list[Ticket]:
        """User's tickets with category + rating for display."""
        stmt = (
            select(Ticket)
            .where(Ticket.author_id == author_id)
            .options(
                selectinload(Ticket.category),
                selectinload(Ticket.rating),
            )
            .order_by(Ticket.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_new_tickets(self, limit: int = 50) -> list[Ticket]:
        stmt = (
            select(Ticket)
            .where(Ticket.status == TicketStatus.NEW)
            .options(selectinload(Ticket.category))
            .order_by(Ticket.created_at.asc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_operator_in_progress(self, operator_id: int, limit: int = 50) -> list[Ticket]:
        stmt = (
            select(Ticket)
            .where(
                and_(
                    Ticket.operator_id == operator_id,
                    Ticket.status.in_([TicketStatus.IN_PROGRESS, TicketStatus.ANSWERED]),
                )
            )
            .options(selectinload(Ticket.category))
            .order_by(Ticket.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_operator_history(self, operator_id: int, limit: int = 50) -> list[Ticket]:
        stmt = (
            select(Ticket)
            .where(
                and_(
                    Ticket.operator_id == operator_id,
                    Ticket.status == TicketStatus.CLOSED,
                )
            )
            .options(
                selectinload(Ticket.category),
                selectinload(Ticket.rating),
            )
            .order_by(Ticket.closed_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def assign_operator(self, ticket_id: int, operator_id: int) -> Optional[Ticket]:
        ticket = await self.get_by_id(ticket_id)
        if ticket:
            ticket.operator_id = operator_id
            ticket.status = TicketStatus.IN_PROGRESS
            await self.session.flush()
        return ticket

    async def update_status(self, ticket_id: int, status: TicketStatus) -> Optional[Ticket]:
        ticket = await self.get_by_id(ticket_id)
        if ticket:
            ticket.status = status
            if status == TicketStatus.CLOSED:
                ticket.closed_at = datetime.utcnow()
            await self.session.flush()
        return ticket

    async def count_by_status(self, status: TicketStatus) -> int:
        result = await self.session.execute(
            select(func.count(Ticket.id)).where(Ticket.status == status)
        )
        return result.scalar_one()

    async def count_all(self) -> int:
        result = await self.session.execute(select(func.count(Ticket.id)))
        return result.scalar_one()

    async def count_by_category(self) -> dict[str, int]:
        from database.models.category import Category
        result = await self.session.execute(
            select(Category.name, func.count(Ticket.id))
            .join(Category, Ticket.category_id == Category.id)
            .group_by(Category.name)
        )
        return dict(result.all())

    async def get_all_for_export(self) -> list[Ticket]:
        """Export with explicit loading — only needed relationships."""
        stmt = (
            select(Ticket)
            .options(
                selectinload(Ticket.author),
                selectinload(Ticket.operator),
                selectinload(Ticket.category),
                selectinload(Ticket.rating),
            )
            .order_by(Ticket.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_all_closed(self, limit: int = 100) -> list[Ticket]:
        stmt = (
            select(Ticket)
            .where(Ticket.status == TicketStatus.CLOSED)
            .options(selectinload(Ticket.rating))
            .order_by(Ticket.closed_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
