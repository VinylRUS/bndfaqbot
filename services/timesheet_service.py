from __future__ import annotations

import re
import logging
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from database.models.role import RoleEnum
from database.models.timesheet_period import TimesheetPeriod, EmployeeType, PeriodStatus
from database.models.timesheet_entry import TimesheetEntry
from database.models.user import User
from database.repositories.timesheet_period_repo import TimesheetPeriodRepository
from database.repositories.timesheet_entry_repo import TimesheetEntryRepository
from database.repositories.user_repo import UserRepository
from database.repositories.bot_setting_repo import BotSettingRepository

logger = logging.getLogger(__name__)


class TimesheetService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.period_repo = TimesheetPeriodRepository(session)
        self.entry_repo = TimesheetEntryRepository(session)
        self.user_repo = UserRepository(session)

    # ── Period management ──────────────────────────────────────────

    async def create_period(
        self,
        year: int,
        month: int,
        start_day: int,
        end_day: int,
        employee_type: EmployeeType,
        created_by: int,
        responsible_operator_id: Optional[int] = None,
    ) -> TimesheetPeriod:
        start_date = date(year, month, start_day)
        end_date = date(year, month, end_day)
        deadline = datetime(year, month, end_day, 23, 59, 59) + timedelta(days=2)

        return await self.period_repo.create(
            year=year,
            month=month,
            start_date=start_date,
            end_date=end_date,
            deadline=deadline,
            employee_type=employee_type,
            created_by=created_by,
            responsible_operator_id=responsible_operator_id,
        )

    async def get_open_periods_for_user(self, user_id: int) -> list[TimesheetPeriod]:
        user = await self.user_repo.get_by_telegram_id_with_role(user_id)
        if not user or not user.employee_type:
            return []
        return await self.period_repo.get_active_by_employee_type(
            EmployeeType(user.employee_type.value if hasattr(user.employee_type, "value") else user.employee_type)
        )

    async def get_all_periods(self) -> list[TimesheetPeriod]:
        return await self.period_repo.get_all()

    async def get_collecting_periods(self) -> list[TimesheetPeriod]:
        return await self.period_repo.get_collecting()

    async def get_period_by_id(self, period_id: int) -> Optional[TimesheetPeriod]:
        return await self.period_repo.get_by_id(period_id)

    async def mark_completed(self, period_id: int) -> Optional[TimesheetPeriod]:
        return await self.period_repo.update_status(period_id, PeriodStatus.COMPLETED)

    async def mark_exported(self, period_id: int, google_url: str) -> Optional[TimesheetPeriod]:
        period = await self.period_repo.update_status(period_id, PeriodStatus.EXPORTED)
        if period:
            await self.period_repo.update_google_url(period_id, google_url)
        return period

    # ── Submission ─────────────────────────────────────────────────

    async def generate_template(self, period_id: int, user_id: int) -> str:
        """Generate a pre-filled template for the user to fill in."""
        period = await self.period_repo.get_by_id(period_id)
        if not period:
            return "Период не найден."

        user = await self.user_repo.get_by_telegram_id(user_id)
        full_name = user.full_name if user and user.full_name else ""

        lines = [full_name]
        current = period.start_date
        while current <= period.end_date:
            lines.append(f"{current.strftime('%d.%m.%Y')}  ")
            current += timedelta(days=1)

        return "\n".join(lines)

    async def parse_and_save_submission(
        self, period_id: int, user_id: int, text: str
    ) -> dict:
        """Parse user-submitted timesheet text and save entries.

        Returns dict with 'success' bool and 'errors' list or 'entries' count.
        """
        period = await self.period_repo.get_by_id(period_id)
        if not period:
            return {"success": False, "errors": ["Период не найден."]}

        # Check if still editable (12 hours before deadline)
        now = datetime.utcnow()
        if now >= period.deadline - timedelta(hours=12):
            return {"success": False, "errors": ["Срок сдачи истёк, редактирование невозможно."]}

        lines = text.strip().split("\n")
        if len(lines) < 2:
            return {"success": False, "errors": ["Слишком мало строк. Отправьте ФИО + даты."]}

        # First line = ФИО
        full_name = lines[0].strip()
        errors = []
        entries = []

        # Validate and parse each date line
        date_lines = lines[1:]
        for i, line in enumerate(date_lines, start=2):
            line = line.strip()
            if not line:
                continue

            parsed = _parse_timesheet_line(line)
            if parsed is None:
                errors.append(f"Строка {i}: не удалось распознать формат: «{line}»")
                continue

            # Validate date is within period
            if not (period.start_date <= parsed["date"] <= period.end_date):
                errors.append(f"Строка {i}: дата {parsed['date']} вне периода")
                continue

            entries.append(
                TimesheetEntry(
                    period_id=period_id,
                    user_id=user_id,
                    date=parsed["date"],
                    start_hour=parsed.get("start_hour"),
                    end_hour=parsed.get("end_hour"),
                    workplace=parsed.get("workplace"),
                    has_lunch=parsed.get("has_lunch", False),
                    is_day_off=parsed.get("is_day_off", False),
                    hours_worked=parsed.get("hours_worked", 0),
                )
            )

        if errors:
            return {"success": False, "errors": errors}

        if not entries:
            return {"success": False, "errors": ["Нет распознанных строк. Проверьте формат."]}

        # Delete previous entries and save new ones
        await self.entry_repo.delete_by_period_and_user(period_id, user_id)
        await self.entry_repo.bulk_create(entries)

        # Save full_name to user profile
        if full_name:
            user = await self.user_repo.get_by_telegram_id(user_id)
            if user:
                user.full_name = full_name

        # Check if all users have submitted
        await self._check_period_completion(period_id)

        total_hours = sum(e.hours_worked or 0 for e in entries)
        return {"success": True, "entries_count": len(entries), "total_hours": total_hours}

    async def get_user_submission_text(self, period_id: int, user_id: int) -> str:
        """Reconstruct the submission text for a user (for editing)."""
        period = await self.period_repo.get_by_id(period_id)
        user = await self.user_repo.get_by_telegram_id(user_id)
        entries = await self.entry_repo.get_by_period_and_user(period_id, user_id)

        if not entries:
            return await self.generate_template(period_id, user_id)

        full_name = user.full_name if user and user.full_name else ""
        lines = [full_name]

        for entry in entries:
            if entry.is_day_off:
                lines.append(f"{entry.date.strftime('%d.%m.%Y')}  Выходной")
            else:
                lunch_str = "обед" if entry.has_lunch else "без обеда"
                workplace = entry.workplace or ""
                time_str = f"{entry.start_hour}-{entry.end_hour}" if entry.start_hour and entry.end_hour else ""
                lines.append(f"{entry.date.strftime('%d.%m.%Y')}  {time_str} {workplace} {lunch_str}".strip())

        return "\n".join(lines)

    async def has_user_submitted(self, period_id: int, user_id: int) -> bool:
        entries = await self.entry_repo.get_by_period_and_user(period_id, user_id)
        return len(entries) > 0

    async def get_submission_status(self, period_id: int) -> dict:
        """Get submission status for a period."""
        period = await self.period_repo.get_by_id(period_id)
        if not period:
            return {}

        submitted_ids = await self.entry_repo.get_submitted_user_ids(period_id)

        # Get all users of this employee type
        emp_type = EmployeeType(period.employee_type.value if hasattr(period.employee_type, "value") else period.employee_type)
        all_users = await self.user_repo.get_all(limit=500)
        # Filter by employee_type
        target_users = [u for u in all_users if u.employee_type == emp_type]

        total = len(target_users)
        submitted = len([u for u in target_users if u.telegram_id in submitted_ids])
        missing = [u for u in target_users if u.telegram_id not in submitted_ids]

        return {
            "total": total,
            "submitted": submitted,
            "missing": missing,
            "period": period,
        }

    async def _check_period_completion(self, period_id: int) -> None:
        """Check if all required users have submitted, mark period as completed."""
        status = await self.get_submission_status(period_id)
        if status.get("total", 0) > 0 and status.get("submitted", 0) >= status.get("total", 0):
            await self.period_repo.update_status(period_id, PeriodStatus.COMPLETED)

    # ── Reminders ──────────────────────────────────────────────────

    async def get_periods_for_reminder(self) -> dict:
        """Get periods that need reminders sent.
        
        Returns dict categorizing periods by reminder type.
        """
        now = datetime.utcnow()
        collecting = await self.period_repo.get_collecting()

        result = {
            "two_days_before": [],   # deadline in 2 days
            "deadline_day": [],      # deadline today
            "half_day_before": [],   # deadline in 12 hours
        }

        for period in collecting:
            delta = period.deadline - now
            if timedelta(days=1) < delta <= timedelta(days=2):
                result["two_days_before"].append(period)
            elif timedelta(hours=0) < delta <= timedelta(days=1):
                result["deadline_day"].append(period)
            elif timedelta(hours=0) < delta <= timedelta(hours=12):
                result["half_day_before"].append(period)

        return result

    async def get_users_for_period(self, period_id: int) -> list[User]:
        """Get all users who should submit for a period."""
        period = await self.period_repo.get_by_id(period_id)
        if not period:
            return []
        emp_type = EmployeeType(period.employee_type.value if hasattr(period.employee_type, "value") else period.employee_type)
        all_users = await self.user_repo.get_all(limit=500)
        return [u for u in all_users if u.employee_type == emp_type]

    # ── Settings ───────────────────────────────────────────────────

    async def get_google_settings(self) -> dict:
        repo = BotSettingRepository(self.session)
        spreadsheet_id = await repo.get("google_spreadsheet_id")
        credentials_json = await repo.get("google_credentials_json")
        return {
            "spreadsheet_id": spreadsheet_id or "",
            "credentials_json": credentials_json or "",
        }

    async def set_google_settings(self, spreadsheet_id: str, credentials_json: str) -> None:
        repo = BotSettingRepository(self.session)
        await repo.set("google_spreadsheet_id", spreadsheet_id)
        await repo.set("google_credentials_json", credentials_json)


# ── Parsing helpers ────────────────────────────────────────────────

def _parse_timesheet_line(line: str) -> dict | None:
    """Parse a single timesheet line.

    Supported formats:
      15.06.2026  Выходной
      15.06.2026  9-19 Склад обед
      15.06.2026  9-18 Склад без обеда
      15.06.2026  09-19 Склад обед
    """
    line = line.strip()
    if not line:
        return None

    # Match date at the beginning
    date_match = re.match(r"(\d{2}\.\d{2}\.\d{4})\s+(.*)", line)
    if not date_match:
        return None

    date_str = date_match.group(1)
    rest = date_match.group(2).strip()

    try:
        parsed_date = datetime.strptime(date_str, "%d.%m.%Y").date()
    except ValueError:
        return None

    # Day off
    if rest.lower() == "выходной":
        return {
            "date": parsed_date,
            "is_day_off": True,
            "start_hour": None,
            "end_hour": None,
            "workplace": None,
            "has_lunch": False,
            "hours_worked": 0,
        }

    # Working day: time range + workplace + lunch
    time_match = re.match(r"(\d{1,2})-(\d{1,2})\s+(.*)", rest)
    if not time_match:
        return None

    start_hour = int(time_match.group(1))
    end_hour = int(time_match.group(2))
    details = time_match.group(3).strip()

    # Determine lunch
    has_lunch = bool(re.search(r"\bобед\b", details.lower())) and not re.search(r"\bбез\s+обед", details.lower())

    # Extract workplace (remove lunch part)
    workplace = re.sub(r"\s*(без\s+)?обед\s*", "", details, flags=re.IGNORECASE).strip()
    workplace = re.sub(r"\s+$", "", workplace)

    # Calculate hours
    hours = end_hour - start_hour
    if has_lunch:
        hours -= 1

    return {
        "date": parsed_date,
        "is_day_off": False,
        "start_hour": start_hour,
        "end_hour": end_hour,
        "workplace": workplace or None,
        "has_lunch": has_lunch,
        "hours_worked": max(hours, 0),
    }
