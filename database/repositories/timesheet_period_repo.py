from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.timesheet_period import TimesheetPeriod, EmployeeType, PeriodStatus


class TimesheetPeriodRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, period_id: int) -> Optional[TimesheetPeriod]:
        result = await self.session.execute(
            select(TimesheetPeriod).where(TimesheetPeriod.id == period_id)
        )
        return result.scalar_one_or_none()

    async def get_active_by_employee_type(self, employee_type: EmployeeType) -> list[TimesheetPeriod]:
        result = await self.session.execute(
            select(TimesheetPeriod)
            .where(
                and_(
                    TimesheetPeriod.employee_type == employee_type,
                    TimesheetPeriod.status == PeriodStatus.COLLECTING,
                )
            )
            .order_by(TimesheetPeriod.deadline.asc())
        )
        return list(result.scalars().all())

    async def get_all(self, limit: int = 50) -> list[TimesheetPeriod]:
        result = await self.session.execute(
            select(TimesheetPeriod)
            .order_by(TimesheetPeriod.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_collecting(self) -> list[TimesheetPeriod]:
        result = await self.session.execute(
            select(TimesheetPeriod)
            .where(TimesheetPeriod.status == PeriodStatus.COLLECTING)
            .order_by(TimesheetPeriod.deadline.asc())
        )
        return list(result.scalars().all())

    async def create(
        self,
        year: int,
        month: int,
        start_date: date,
        end_date: date,
        deadline: datetime,
        employee_type: EmployeeType,
        created_by: int,
        responsible_operator_id: Optional[int] = None,
    ) -> TimesheetPeriod:
        period = TimesheetPeriod(
            year=year,
            month=month,
            start_date=start_date,
            end_date=end_date,
            deadline=deadline,
            employee_type=employee_type,
            created_by=created_by,
            responsible_operator_id=responsible_operator_id,
        )
        self.session.add(period)
        await self.session.flush()
        return period

    async def update_status(self, period_id: int, status: PeriodStatus) -> Optional[TimesheetPeriod]:
        period = await self.get_by_id(period_id)
        if period:
            period.status = status
            await self.session.flush()
        return period

    async def update_google_url(self, period_id: int, url: str) -> Optional[TimesheetPeriod]:
        period = await self.get_by_id(period_id)
        if period:
            period.google_sheet_url = url
            await self.session.flush()
        return period
