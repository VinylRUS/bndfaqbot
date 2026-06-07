from __future__ import annotations

from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, Text, DateTime, ForeignKey, Enum as SAEnum, Integer, BigInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.models.base import Base

if TYPE_CHECKING:
    from database.models.user import User
    from database.models.category import Category
    from database.models.ticket_message import TicketMessage
    from database.models.rating import Rating

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
    author_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.telegram_id"), nullable=False
    )
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        SAEnum(TicketStatus, name="ticket_status_enum", native_enum=True),
        default=TicketStatus.NEW,
        nullable=False,
    )
    operator_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("users.telegram_id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    closed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # lazy="select" — loaded on demand only, no auto-cascade
    author: Mapped["User"] = relationship(
        back_populates="tickets", foreign_keys=[author_id], lazy="select"
    )
    operator: Mapped[Optional["User"]] = relationship(
        back_populates="assigned_tickets", foreign_keys=[operator_id], lazy="select"
    )
    category: Mapped["Category"] = relationship(back_populates="tickets", lazy="select")
    messages: Mapped[list["TicketMessage"]] = relationship(
        back_populates="ticket", lazy="select", order_by="TicketMessage.created_at"
    )
    rating: Mapped[Optional["Rating"]] = relationship(back_populates="ticket", lazy="select")

    def __repr__(self) -> str:
        return f"<Ticket id={self.id} number={self.number} status={self.status}>"
