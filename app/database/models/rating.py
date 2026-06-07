from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import SmallInteger, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.models.base import Base

if TYPE_CHECKING:
    from app.database.models.user import User
    from app.database.models.ticket import Ticket


class Rating(Base):
    __tablename__ = "ratings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ticket_id: Mapped[int] = mapped_column(
        ForeignKey("tickets.id"), unique=True, nullable=False
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    score: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    ticket: Mapped["Ticket"] = relationship(back_populates="rating", lazy="selectin")
    user: Mapped["User"] = relationship(back_populates="ratings_given", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Rating id={self.id} ticket_id={self.ticket_id} score={self.score}>"
