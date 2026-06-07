from __future__ import annotations

from sqlalchemy import String, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.models.base import Base

import enum


class RoleEnum(str, enum.Enum):
    ADMIN = "admin"
    OPERATOR = "operator"
    USER = "user"


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(
        SAEnum(RoleEnum, name="role_enum", native_enum=True),
        unique=True,
        nullable=False,
    )

    users: Mapped[list["User"]] = relationship(back_populates="role", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Role id={self.id} name={self.name}>"
