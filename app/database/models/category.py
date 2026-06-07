from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.models.base import Base

if TYPE_CHECKING:
    from app.database.models.ticket import Ticket


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    emoji: Mapped[str] = mapped_column(String(10), nullable=False, default="")
    parent_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("categories.id"), nullable=True
    )

    parent: Mapped[Optional["Category"]] = relationship(
        remote_side="Category.id", back_populates="children", lazy="selectin"
    )
    children: Mapped[list["Category"]] = relationship(back_populates="parent", lazy="selectin")
    tickets: Mapped[list["Ticket"]] = relationship(back_populates="category", lazy="selectin")

    @property
    def is_topic(self) -> bool:
        return self.parent_id is not None

    @property
    def full_name(self) -> str:
        if self.emoji:
            return f"{self.emoji} {self.name}"
        return self.name

    def __repr__(self) -> str:
        return f"<Category id={self.id} name={self.name}>"
