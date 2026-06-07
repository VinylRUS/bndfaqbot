from __future__ import annotations

import json
import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from database.repositories.timesheet_entry_repo import TimesheetEntryRepository
from database.repositories.timesheet_period_repo import TimesheetPeriodRepository
from database.repositories.bot_setting_repo import BotSettingRepository
from database.repositories.user_repo import UserRepository
from database.models.timesheet_period import PeriodStatus

logger = logging.getLogger(__name__)


class GoogleSheetsService:
    """Export timesheet data to Google Sheets using gspread."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.setting_repo = BotSettingRepository(session)
        self.period_repo = TimesheetPeriodRepository(session)
        self.entry_repo = TimesheetEntryRepository(session)
        self.user_repo = UserRepository(session)

    async def _get_client(self):
        """Create gspread client from stored credentials."""
        try:
            import gspread
            from google.oauth2.service_account import Credentials
        except ImportError:
            logger.error("gspread or google-auth not installed. Run: pip install gspread google-auth")
            return None, None

        credentials_json = await self.setting_repo.get("google_credentials_json")
        if not credentials_json:
            return None, None

        try:
            info = json.loads(credentials_json)
            scopes = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive",
            ]
            creds = Credentials.from_service_account_info(info, scopes=scopes)
            client = gspread.authorize(creds)
            return client, creds
        except Exception as e:
            logger.error("Failed to create Google client: %s", e)
            return None, None

    async def export_period(self, period_id: int) -> Optional[str]:
        """Export a period's timesheet data to Google Sheets.

        Returns the URL of the sheet, or None on failure.
        """
        client, _ = await self._get_client()
        if not client:
            return None

        spreadsheet_id = await self.setting_repo.get("google_spreadsheet_id")
        if not spreadsheet_id:
            return None

        period = await self.period_repo.get_by_id(period_id)
        if not period:
            return None

        entries = await self.entry_repo.get_by_period(period_id)
        if not entries:
            return None

        # Group entries by user
        user_entries: dict[int, list] = {}
        for entry in entries:
            if entry.user_id not in user_entries:
                user_entries[entry.user_id] = []
            user_entries[entry.user_id].append(entry)

        # Month names in Russian
        month_names = [
            "", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
            "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
        ]
        sheet_title = f"{month_names[period.month]} {period.year}"

        try:
            spreadsheet = client.open_by_key(spreadsheet_id)
        except Exception as e:
            logger.error("Failed to open spreadsheet: %s", e)
            return None

        # Create or get worksheet
        try:
            worksheet = spreadsheet.worksheet(sheet_title)
        except gspread.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(title=sheet_title, rows=100, cols=50)

        # Clear existing data
        worksheet.clear()

        # Build data rows
        rows = []
        col = 1  # 1-indexed

        for user_id, user_entry_list in user_entries.items():
            user = await self.user_repo.get_by_telegram_id(user_id)
            user_name = user.full_name if user and user.full_name else (user.display_name if user else str(user_id))

            # Header row: user name
            worksheet.update_cell(1, col, user_name)

            # Sub-header: Дата | Часы | Место | Обед
            worksheet.update_cell(2, col, "Дата")
            worksheet.update_cell(2, col + 1, "Часы")
            worksheet.update_cell(2, col + 2, "Место")
            worksheet.update_cell(2, col + 3, "Обед")

            # Data rows
            total_hours = 0.0
            row = 3
            for entry in user_entry_list:
                date_str = entry.date.strftime("%d.%m.%Y")
                if entry.is_day_off:
                    worksheet.update_cell(row, col, date_str)
                    worksheet.update_cell(row, col + 1, "Выходной")
                    worksheet.update_cell(row, col + 2, "")
                    worksheet.update_cell(row, col + 3, "")
                else:
                    time_str = f"{entry.start_hour}-{entry.end_hour}" if entry.start_hour and entry.end_hour else ""
                    lunch_str = "Да" if entry.has_lunch else "Нет"
                    worksheet.update_cell(row, col, date_str)
                    worksheet.update_cell(row, col + 1, time_str)
                    worksheet.update_cell(row, col + 2, entry.workplace or "")
                    worksheet.update_cell(row, col + 3, lunch_str)
                    total_hours += entry.hours_worked or 0
                row += 1

            # Total hours row
            worksheet.update_cell(row, col, "Итого часов:")
            worksheet.update_cell(row, col + 1, str(total_hours))

            col += 5  # 4 columns + 1 gap

        # Update period status
        period.status = PeriodStatus.EXPORTED
        period.google_sheet_url = spreadsheet.url
        await self.session.flush()

        return spreadsheet.url
