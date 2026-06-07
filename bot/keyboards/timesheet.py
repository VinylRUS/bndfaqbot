from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from database.models.timesheet_period import TimesheetPeriod, EmployeeType


def get_timesheet_admin_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="📋 Создать период", callback_data="ts_create_period")],
        [InlineKeyboardButton(text="📊 Статус сбора", callback_data="ts_status")],
        [InlineKeyboardButton(text="📤 Выгрузить в Google", callback_data="ts_export")],
        [InlineKeyboardButton(text="👤 Настройки сотрудников", callback_data="ts_employees")],
        [InlineKeyboardButton(text="⚙ Google настройки", callback_data="ts_google_settings")],
        [InlineKeyboardButton(text="🔙 В меню", callback_data="back_to_menu")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_employee_type_keyboard(prefix: str = "") -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="👷 Штатный", callback_data=f"{prefix}full_time")],
        [InlineKeyboardButton(text="🔧 Нештатный", callback_data=f"{prefix}part_time")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="ts_create_period")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_periods_keyboard(periods: list[TimesheetPeriod]) -> InlineKeyboardMarkup:
    buttons = []
    for period in periods:
        emp_label = "Штатные" if period.employee_type == EmployeeType.FULL_TIME else "Нештатные"
        text = f"📊 {period.start_date.strftime('%d.%m')}–{period.end_date.strftime('%d.%m')} ({emp_label})"
        buttons.append(
            [InlineKeyboardButton(text=text, callback_data=f"ts_period_{period.id}")]
        )
    if not buttons:
        buttons.append([InlineKeyboardButton(text="Нет открытых периодов", callback_data="noop")])
    buttons.append(
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_user_periods_keyboard(periods: list[TimesheetPeriod]) -> InlineKeyboardMarkup:
    buttons = []
    for period in periods:
        emp_label = "Штатные" if period.employee_type == EmployeeType.FULL_TIME else "Нештатные"
        deadline_str = period.deadline.strftime('%d.%m')
        text = f"🕐 {period.start_date.strftime('%d.%m')}–{period.end_date.strftime('%d.%m')} (до {deadline_str})"
        buttons.append(
            [InlineKeyboardButton(text=text, callback_data=f"ts_submit_{period.id}")]
        )
    if not buttons:
        buttons.append([InlineKeyboardButton(text="Нет открытых периодов", callback_data="noop")])
    buttons.append(
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_submission_keyboard(period_id: int, has_submitted: bool) -> InlineKeyboardMarkup:
    buttons = []
    if has_submitted:
        buttons.append(
            [InlineKeyboardButton(text="✏ Изменить данные", callback_data=f"ts_edit_{period_id}")]
        )
    buttons.append(
        [InlineKeyboardButton(text="🔙 К периодам", callback_data="ts_my_periods")]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_period_detail_keyboard(period_id: int, is_collecting: bool) -> InlineKeyboardMarkup:
    buttons = []
    if is_collecting:
        buttons.append(
            [InlineKeyboardButton(text="📊 Кто сдал", callback_data=f"ts_who_{period_id}")]
        )
    buttons.append(
        [InlineKeyboardButton(text="🔙 К списку", callback_data="ts_status")]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_employees_keyboard(users: list) -> InlineKeyboardMarkup:
    buttons = []
    for user in users:
        emp_type = "Штатный" if user.employee_type and user.employee_type.value == "full_time" else (
            "Нештатный" if user.employee_type else "Не задан"
        )
        workplace = user.workplace or "—"
        text = f"{user.display_name} | {emp_type} | {workplace}"
        buttons.append(
            [InlineKeyboardButton(text=_truncate(text, 50), callback_data=f"ts_emp_{user.id}")]
        )
    buttons.append(
        [InlineKeyboardButton(text="🔙 Назад", callback_data="ts_admin")]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_employee_edit_keyboard(user_id: int) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="👷 Тип сотрудника", callback_data=f"ts_emptype_{user_id}")],
        [InlineKeyboardButton(text="🏭 Место работы", callback_data=f"ts_empwork_{user_id}")],
        [InlineKeyboardButton(text="📝 ФИО", callback_data=f"ts_empname_{user_id}")],
        [InlineKeyboardButton(text="🔙 К списку", callback_data="ts_employees")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_export_periods_keyboard(periods: list[TimesheetPeriod]) -> InlineKeyboardMarkup:
    buttons = []
    for period in periods:
        emp_label = "Штатные" if period.employee_type == EmployeeType.FULL_TIME else "Нештатные"
        status_emoji = "✅" if period.status == "completed" else "🔄"
        text = f"{status_emoji} {period.start_date.strftime('%d.%m')}–{period.end_date.strftime('%d.%m')} ({emp_label})"
        buttons.append(
            [InlineKeyboardButton(text=text, callback_data=f"ts_doexport_{period.id}")]
        )
    if not buttons:
        buttons.append([InlineKeyboardButton(text="Нет периодов для выгрузки", callback_data="noop")])
    buttons.append(
        [InlineKeyboardButton(text="🔙 Назад", callback_data="ts_admin")]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."
