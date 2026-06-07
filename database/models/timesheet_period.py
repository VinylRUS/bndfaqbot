from __future__ import annotations

import enum
from datetime import date, datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, Date, DateTime, Integer, Float, Boolean, BigInteger
from sqlalchemy import ForeignKey, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.models.base import Base

if TYPE_CHECKING:
    from database.models.user import User
    from database.models.timesheet_entry import TimesheetEntry


class EmployeeType(str, enum.Enum):
    FULL_TIME = "full_time"   # штатный
    PART_TIME = "part_time"   # нештатный


class PeriodStatus(str, enum.Enum):
    COLLECTING = "collecting"  # сбор идёт
    COMPLETED = "completed"   # все сдали
    EXPORTED = "exported"     # выгружено в Google


class TimesheetPeriod(Base):
    __tablename__ = "timesheet_periods"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    employee_type: Mapped[str] = mapped_column(
        SAEnum(EmployeeType, name="employee_type_enum", native_enum=True),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        SAEnum(PeriodStatus, name="period_status_enum", native_enum=True),
        default=PeriodStatus.COLLECTING,
        nullable=False,
    )
    responsible_operator_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("users.telegram_id"), nullable=True
    )
    created_by: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.telegram_id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    google_sheet_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    entries: Mapped[list["TimesheetEntry"]] = relationship(
        back_populates="period", lazy="select"
    )
    responsible_operator: Mapped[Optional["User"]] = relationship(
        foreign_keys=[responsible_operator_id], lazy="select"
    )
    creator: Mapped["User"] = relationship(foreign_keys=[created_by], lazy="select")

    def __repr__(self) -> str:
        return f"<TimesheetPeriod id={self.id} {self.start_date}-{self.end_date}>"
