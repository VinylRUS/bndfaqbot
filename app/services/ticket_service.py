from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.ticket import Ticket, TicketStatus
from app.database.models.user import User
from app.database.repositories.ticket_repo import TicketRepository
from app.database.repositories.ticket_message_repo import TicketMessageRepository
from app.database.repositories.audit_log_repo import AuditLogRepository


class TicketService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.ticket_repo = TicketRepository(session)
        self.message_repo = TicketMessageRepository(session)
        self.audit_repo = AuditLogRepository(session)

    async def create_ticket(self, author_id: int, category_id: int, text: str) -> Ticket:
        ticket = await self.ticket_repo.create(
            author_id=author_id,
            category_id=category_id,
            text=text,
        )
        await self.message_repo.create(
            ticket_id=ticket.id,
            sender_id=author_id,
            text=text,
        )
        return ticket

    async def get_by_id(self, ticket_id: int) -> Optional[Ticket]:
        return await self.ticket_repo.get_by_id(ticket_id)

    async def get_by_number(self, number: int) -> Optional[Ticket]:
        return await self.ticket_repo.get_by_number(number)

    async def get_user_tickets(self, author_id: int) -> list[Ticket]:
        return await self.ticket_repo.get_user_tickets(author_id)

    async def get_new_tickets(self) -> list[Ticket]:
        return await self.ticket_repo.get_new_tickets()

    async def get_operator_active(self, operator_id: int) -> list[Ticket]:
        return await self.ticket_repo.get_operator_in_progress(operator_id)

    async def get_operator_history(self, operator_id: int) -> list[Ticket]:
        return await self.ticket_repo.get_operator_history(operator_id)

    async def assign_operator(self, ticket_id: int, operator_id: int) -> Optional[Ticket]:
        ticket = await self.ticket_repo.get_by_id(ticket_id)
        if not ticket:
            return None
        if ticket.status != TicketStatus.NEW:
            return None
        ticket = await self.ticket_repo.assign_operator(ticket_id, operator_id)
        if ticket:
            await self.audit_repo.create(
                user_id=operator_id,
                role="operator",
                action="assign_ticket",
                object_type="ticket",
                object_id=ticket_id,
                details=f"Ticket #{ticket.number} assigned to operator",
            )
        return ticket

    async def add_message(self, ticket_id: int, sender_id: int, text: str) -> Optional[dict]:
        ticket = await self.ticket_repo.get_by_id(ticket_id)
        if not ticket:
            return None
        message = await self.message_repo.create(
            ticket_id=ticket_id,
            sender_id=sender_id,
            text=text,
        )
        if ticket.status == TicketStatus.IN_PROGRESS:
            await self.ticket_repo.update_status(ticket_id, TicketStatus.ANSWERED)
        return {"message": message, "ticket": ticket}

    async def close_ticket(self, ticket_id: int, operator_id: int) -> Optional[Ticket]:
        ticket = await self.ticket_repo.update_status(ticket_id, TicketStatus.CLOSED)
        if ticket:
            await self.audit_repo.create(
                user_id=operator_id,
                role="operator",
                action="close_ticket",
                object_type="ticket",
                object_id=ticket_id,
                details=f"Ticket #{ticket.number} closed",
            )
        return ticket

    async def set_status(self, ticket_id: int, status: TicketStatus) -> Optional[Ticket]:
        return await self.ticket_repo.update_status(ticket_id, status)

    async def get_ticket_messages(self, ticket_id: int) -> list:
        return await self.message_repo.get_by_ticket(ticket_id)

    async def get_all_for_export(self) -> list[Ticket]:
        return await self.ticket_repo.get_all_for_export()

    async def count_by_status(self, status: TicketStatus) -> int:
        return await self.ticket_repo.count_by_status(status)

    async def count_all(self) -> int:
        return await self.ticket_repo.count_all()

    async def count_by_category(self) -> dict[str, int]:
        return await self.ticket_repo.count_by_category()
