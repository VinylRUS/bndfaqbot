from __future__ import annotations

from datetime import date, datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, Date, DateTime, Integer, Float, Boolean, BigInteger, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.models.base import Base

if TYPE_CHECKING:
    from database.models.timesheet_period import TimesheetPeriod
    from database.models.user import User


class TimesheetEntry(Base):
    __tablename__ = "timesheet_entries"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    period_id: Mapped[int] = mapped_column(
        ForeignKey("timesheet_periods.id"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.telegram_id"), nullable=False
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    start_hour: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    end_hour: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    workplace: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    has_lunch: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_day_off: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    hours_worked: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    period: Mapped["TimesheetPeriod"] = relationship(back_populates="entries", lazy="select")
    user: Mapped["User"] = relationship(lazy="select")

    def __repr__(self) -> str:
        return f"<TimesheetEntry id={self.id} date={self.date}>"
