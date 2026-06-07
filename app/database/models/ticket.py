from __future__ import annotations

from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, Text, DateTime, ForeignKey, Enum as SAEnum, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.models.base import Base

if TYPE_CHECKING:
    from app.database.models.user import User
    from app.database.models.category import Category
    from app.database.models.ticket_message import TicketMessage
    from app.database.models.rating import Rating

import enum


class TicketStatus(str, enum.Enum):
    NEW = "NEW"
    IN_PROGRESS = "IN_PROGRESS"
    ANSWERED = "ANSWERED"
    CLOSED = "CLOSED"


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    number: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        SAEnum(TicketStatus, name="ticket_status_enum", native_enum=True),
        default=TicketStatus.NEW,
        nullable=False,
    )
    operator_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    closed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    author: Mapped["User"] = relationship(
        back_populates="tickets", foreign_keys=[author_id], lazy="selectin"
    )
    operator: Mapped[Optional["User"]] = relationship(
        back_populates="assigned_tickets", foreign_keys=[operator_id], lazy="selectin"
    )
    category: Mapped["Category"] = relationship(back_populates="tickets", lazy="selectin")
    messages: Mapped[list["TicketMessage"]] = relationship(
        back_populates="ticket", lazy="selectin", order_by="TicketMessage.created_at"
    )
    rating: Mapped[Optional["Rating"]] = relationship(back_populates="ticket", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Ticket id={self.id} number={self.number} status={self.status}>"
