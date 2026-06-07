from __future__ import annotations

from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import BigInteger, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.models.base import Base

if TYPE_CHECKING:
    from database.models.role import Role
    from database.models.ticket import Ticket
    from database.models.rating import Rating
    from database.models.audit_log import AuditLog


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), nullable=False)
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    # lazy="select" — loaded on demand only, no auto-cascade
    role: Mapped["Role"] = relationship(back_populates="users", lazy="select")
    tickets: Mapped[list["Ticket"]] = relationship(
        back_populates="author", foreign_keys="Ticket.author_id", lazy="select"
    )
    assigned_tickets: Mapped[list["Ticket"]] = relationship(
        back_populates="operator", foreign_keys="Ticket.operator_id", lazy="select"
    )
    ratings_given: Mapped[list["Rating"]] = relationship(
        back_populates="user", foreign_keys="Rating.user_id", lazy="select"
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        back_populates="user", foreign_keys="AuditLog.user_id", lazy="select"
    )

    @property
    def display_name(self) -> str:
        parts = [self.first_name, self.last_name]
        name = " ".join(p for p in parts if p)
        if self.username:
            name += f" (@{self.username})"
        return name or str(self.telegram_id)

    def __repr__(self) -> str:
        return f"<User id={self.id} telegram_id={self.telegram_id} role={self.role_id}>"
