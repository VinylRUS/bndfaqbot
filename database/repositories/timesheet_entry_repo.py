from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy import select, delete, and_
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.timesheet_entry import TimesheetEntry


class TimesheetEntryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_period_and_user(self, period_id: int, user_id: int) -> list[TimesheetEntry]:
        result = await self.session.execute(
            select(TimesheetEntry)
            .where(
                and_(
                    TimesheetEntry.period_id == period_id,
                    TimesheetEntry.user_id == user_id,
                )
            )
            .order_by(TimesheetEntry.date.asc())
        )
        return list(result.scalars().all())

    async def get_by_period(self, period_id: int) -> list[TimesheetEntry]:
        result = await self.session.execute(
            select(TimesheetEntry)
            .where(TimesheetEntry.period_id == period_id)
            .order_by(TimesheetEntry.user_id, TimesheetEntry.date.asc())
        )
        return list(result.scalars().all())

    async def get_submitted_user_ids(self, period_id: int) -> set[int]:
        result = await self.session.execute(
            select(TimesheetEntry.user_id)
            .where(TimesheetEntry.period_id == period_id)
            .distinct()
        )
        return {row[0] for row in result.all()}

    async def delete_by_period_and_user(self, period_id: int, user_id: int) -> None:
        await self.session.execute(
            delete(TimesheetEntry).where(
                and_(
                    TimesheetEntry.period_id == period_id,
                    TimesheetEntry.user_id == user_id,
                )
            )
        )
        await self.session.flush()

    async def create(
        self,
        period_id: int,
        user_id: int,
        entry_date: date,
        start_hour: Optional[int] = None,
        end_hour: Optional[int] = None,
        workplace: Optional[str] = None,
        has_lunch: bool = False,
        is_day_off: bool = False,
        hours_worked: Optional[float] = None,
    ) -> TimesheetEntry:
        entry = TimesheetEntry(
            period_id=period_id,
            user_id=user_id,
            date=entry_date,
            start_hour=start_hour,
            end_hour=end_hour,
            workplace=workplace,
            has_lunch=has_lunch,
            is_day_off=is_day_off,
            hours_worked=hours_worked,
        )
        self.session.add(entry)
        return entry

    async def bulk_create(self, entries: list[TimesheetEntry]) -> None:
        self.session.add_all(entries)
        await self.session.flush()

    async def count_hours_by_period_and_user(self, period_id: int, user_id: int) -> float:
        from sqlalchemy import func
        result = await self.session.execute(
            select(func.coalesce(func.sum(TimesheetEntry.hours_worked), 0))
            .where(
                and_(
                    TimesheetEntry.period_id == period_id,
                    TimesheetEntry.user_id == user_id,
                )
            )
        )
        return result.scalar_one()
