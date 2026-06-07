from __future__ import annotations

from datetime import datetime, timedelta
import calendar

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.role import RoleEnum
from database.models.timesheet_period import EmployeeType, PeriodStatus
from database.models.user import User
from services.timesheet_service import TimesheetService
from services.user_service import UserService
from bot.states.timesheet_states import TimesheetStates
from bot.keyboards.common import get_main_menu_admin, get_main_menu_operator, get_cancel_keyboard
from bot.keyboards.timesheet import (
    get_timesheet_admin_keyboard,
    get_employee_type_keyboard,
    get_periods_keyboard,
    get_user_periods_keyboard,
    get_submission_keyboard,
    get_period_detail_keyboard,
    get_employees_keyboard,
    get_employee_edit_keyboard,
    get_export_periods_keyboard,
)
from utils.permissions import can_handle_tickets, is_admin


router = Router()


def _is_admin_or_hours_collector(**kwargs) -> bool:
    user_role = kwargs.get("user_role")
    db_user: User | None = kwargs.get("db_user")
    if is_admin(user_role):
        return True
    if db_user and db_user.collects_hours and can_handle_tickets(user_role):
        return True
    return False


# ════════════════════════════════════════════════════════════════════
#  USER: Передать часы
# ════════════════════════════════════════════════════════════════════

@router.message(F.text == "🕐 Передать часы")
async def ts_user_menu(message: Message, **kwargs) -> None:
    session: AsyncSession = kwargs["db_session"]
    ts_service = TimesheetService(session)
    periods = await ts_service.get_open_periods_for_user(message.from_user.id)
    if not periods:
        await message.answer("Нет открытых периодов для сдачи часов.")
        return
    await message.answer("Выберите период:", reply_markup=get_user_periods_keyboard(periods))


@router.callback_query(F.data.startswith("ts_submit_"))
async def ts_user_select_period(callback: CallbackQuery, state: FSMContext, **kwargs) -> None:
    period_id = int(callback.data.split("_")[-1])
    session: AsyncSession = kwargs["db_session"]
    ts_service = TimesheetService(session)

    has_submitted = await ts_service.has_user_submitted(period_id, callback.from_user.id)
    template = await ts_service.generate_template(period_id, callback.from_user.id)

    period = await ts_service.get_period_by_id(period_id)
    deadline_str = period.deadline.strftime('%d.%m.%Y') if period else "?"

    await callback.message.answer(
        f"📅 Период: {period.start_date.strftime('%d.%m')}–{period.end_date.strftime('%d.%m')}\n"
        f"⏰ Дедлайн: {deadline_str}\n\n"
        f"Заполните шаблон ниже (скопируйте, заполните и отправьте):\n\n"
        f"<code>{template}</code>\n\n"
        f"Формат:\n"
        f"• Первая строка — ФИО\n"
        f"• Рабочий день: <code>15.06.2026  9-19 Склад обед</code>\n"
        f"• Без обеда: <code>15.06.2026  9-18 Склад без обеда</code>\n"
        f"• Выходной: <code>15.06.2026  Выходной</code>",
        parse_mode="HTML",
        reply_markup=get_submission_keyboard(period_id, has_submitted),
    )

    if not has_submitted:
        await state.set_state(TimesheetStates.entering_hours)
        await state.update_data(period_id=period_id)

    await callback.answer()


@router.callback_query(F.data.startswith("ts_edit_"))
async def ts_user_edit(callback: CallbackQuery, state: FSMContext, **kwargs) -> None:
    period_id = int(callback.data.split("_")[-1])
    session: AsyncSession = kwargs["db_session"]
    ts_service = TimesheetService(session)

    # Check if within edit window (12 hours before deadline)
    period = await ts_service.get_period_by_id(period_id)
    if not period:
        await callback.answer("Период не найден.", show_alert=True)
        return
    now = datetime.utcnow()
    if now >= period.deadline - timedelta(hours=12):
        await callback.answer("Срок редактирования истёк (менее 12 часов до дедлайна).", show_alert=True)
        return

    previous = await ts_service.get_user_submission_text(period_id, callback.from_user.id)
    await state.set_state(TimesheetStates.entering_hours)
    await state.update_data(period_id=period_id)

    await callback.message.answer(
        f"Ваши предыдущие данные:\n\n<code>{previous}</code>\n\n"
        f"Скопируйте, исправьте и отправьте:",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard(),
    )
    await callback.answer()


@router.message(TimesheetStates.entering_hours, F.text == "❌ Отмена")
async def ts_cancel_entry(message: Message, state: FSMContext, **kwargs) -> None:
    await state.clear()
    user_role: RoleEnum = kwargs.get("user_role", RoleEnum.USER)
    menu = _get_main_menu_by_role(user_role)
    await message.answer("Отменено.", reply_markup=menu())


@router.message(TimesheetStates.entering_hours)
async def ts_submit_hours(message: Message, state: FSMContext, **kwargs) -> None:
    state_data = await state.get_data()
    period_id = state_data.get("period_id")
    if not period_id:
        await message.answer("Ошибка: период не выбран. Начните заново.")
        await state.clear()
        return

    session: AsyncSession = kwargs["db_session"]
    ts_service = TimesheetService(session)
    result = await ts_service.parse_and_save_submission(
        period_id=period_id, user_id=message.from_user.id, text=message.text,
    )

    await state.clear()
    user_role: RoleEnum = kwargs.get("user_role", RoleEnum.USER)
    menu = _get_main_menu_by_role(user_role)

    if result["success"]:
        await message.answer(
            f"✅ Часы приняты!\nЗаписей: {result['entries_count']}\nВсего часов: {result['total_hours']}",
            reply_markup=menu(),
        )
        # Check if all users submitted → notify operator
        await _notify_if_period_complete(period_id, kwargs)
    else:
        errors_text = "\n".join(f"• {e}" for e in result["errors"])
        await message.answer(
            f"❌ Ошибки в формате:\n\n{errors_text}\n\nИсправьте и отправьте заново.",
            reply_markup=get_cancel_keyboard(),
        )
        # Re-enter state for retry
        await state.set_state(TimesheetStates.entering_hours)
        await state.update_data(period_id=period_id)


@router.callback_query(F.data == "ts_my_periods")
async def ts_my_periods(callback: CallbackQuery, **kwargs) -> None:
    session: AsyncSession = kwargs["db_session"]
    ts_service = TimesheetService(session)
    periods = await ts_service.get_open_periods_for_user(callback.from_user.id)
    if not periods:
        await callback.message.answer("Нет открытых периодов для сдачи часов.")
        await callback.answer()
        return
    await callback.message.answer("Выберите период:", reply_markup=get_user_periods_keyboard(periods))
    await callback.answer()


# ════════════════════════════════════════════════════════════════════
#  ADMIN: Управление табелем
# ════════════════════════════════════════════════════════════════════

@router.message(F.text == "🕐 Табель")
async def ts_admin_menu(message: Message, **kwargs) -> None:
    if not _is_admin_or_hours_collector(**kwargs):
        await message.answer("Недостаточно прав.")
        return
    await message.answer("🕐 Управление табелем:", reply_markup=get_timesheet_admin_keyboard())


@router.callback_query(F.data == "ts_admin")
async def ts_admin_callback(callback: CallbackQuery, **kwargs) -> None:
    await callback.message.edit_text("🕐 Управление табелем:", reply_markup=get_timesheet_admin_keyboard())
    await callback.answer()


# ── Создать период ─────────────────────────────────────────────────

@router.callback_query(F.data == "ts_create_period")
async def ts_create_period(callback: CallbackQuery, state: FSMContext, **kwargs) -> None:
    await state.set_state(TimesheetStates.choosing_month)
    await callback.message.answer(
        "Введите месяц и год в формате ММ.ГГГГ (например, 06.2026):",
        reply_markup=get_cancel_keyboard(),
    )
    await callback.answer()


@router.message(TimesheetStates.choosing_month)
async def ts_enter_month(message: Message, state: FSMContext, **kwargs) -> None:
    try:
        parts = message.text.strip().split(".")
        month = int(parts[0])
        year = int(parts[1])
        if not (1 <= month <= 12):
            raise ValueError
    except (ValueError, IndexError):
        await message.answer("Неверный формат. Введите ММ.ГГГГ (например, 06.2026):")
        return

    days_in_month = calendar.monthrange(year, month)[1]
    await state.update_data(year=year, month=month, days_in_month=days_in_month)
    await state.set_state(TimesheetStates.choosing_start_day)
    await message.answer(f"Введите начальный день (1–{days_in_month}):")


@router.message(TimesheetStates.choosing_start_day)
async def ts_enter_start_day(message: Message, state: FSMContext, **kwargs) -> None:
    try:
        day = int(message.text.strip())
        state_data = await state.get_data()
        if not (1 <= day <= state_data["days_in_month"]):
            raise ValueError
    except ValueError:
        state_data = await state.get_data()
        await message.answer(f"Введите число от 1 до {state_data['days_in_month']}:")
        return
    await state.update_data(start_day=day)
    await state.set_state(TimesheetStates.choosing_end_day)
    state_data = await state.get_data()
    await message.answer(f"Введите конечный день ({day}–{state_data['days_in_month']}):")


@router.message(TimesheetStates.choosing_end_day)
async def ts_enter_end_day(message: Message, state: FSMContext, **kwargs) -> None:
    try:
        day = int(message.text.strip())
        state_data = await state.get_data()
        if not (state_data["start_day"] <= day <= state_data["days_in_month"]):
            raise ValueError
    except ValueError:
        state_data = await state.get_data()
        await message.answer(f"Введите число от {state_data['start_day']} до {state_data['days_in_month']}:")
        return

    await state.update_data(end_day=day)
    await state.set_state(TimesheetStates.choosing_employee_type)
    await message.answer("Выберите тип сотрудников:", reply_markup=get_employee_type_keyboard("ts_emptype_"))


@router.callback_query(TimesheetStates.choosing_employee_type, F.data.startswith("ts_emptype_"))
async def ts_select_employee_type(callback: CallbackQuery, state: FSMContext, **kwargs) -> None:
    emp_type_str = callback.data.split("_")[-1]
    emp_type = EmployeeType(emp_type_str)

    state_data = await state.get_data()
    session: AsyncSession = kwargs["db_session"]
    ts_service = TimesheetService(session)

    # Find responsible operator (first operator with collects_hours=True)
    user_service = UserService(session)
    operators = await user_service.get_operators()
    responsible_id = None
    for op in operators:
        if op.collects_hours:
            responsible_id = op.telegram_id
            break

    period = await ts_service.create_period(
        year=state_data["year"],
        month=state_data["month"],
        start_day=state_data["start_day"],
        end_day=state_data["end_day"],
        employee_type=emp_type,
        created_by=callback.from_user.id,
        responsible_operator_id=responsible_id,
    )

    await state.clear()
    emp_label = "Штатные" if emp_type == EmployeeType.FULL_TIME else "Нештатные"
    deadline_str = period.deadline.strftime('%d.%m.%Y')

    await callback.message.edit_text(
        f"✅ Период создан!\n\n"
        f"Даты: {period.start_date.strftime('%d.%m')}–{period.end_date.strftime('%d.%m')}\n"
        f"Тип: {emp_label}\n"
        f"Дедлайн: {deadline_str}",
        reply_markup=None,
    )
    await callback.answer()


# ── Статус сбора ───────────────────────────────────────────────────

@router.callback_query(F.data == "ts_status")
async def ts_status(callback: CallbackQuery, **kwargs) -> None:
    session: AsyncSession = kwargs["db_session"]
    ts_service = TimesheetService(session)
    periods = await ts_service.get_collecting_periods()
    if not periods:
        await callback.message.edit_text("Нет периодов в сборе.", reply_markup=None)
        await callback.answer()
        return
    await callback.message.edit_text("📊 Периоды в сборе:", reply_markup=get_periods_keyboard(periods))
    await callback.answer()


@router.callback_query(F.data.startswith("ts_period_"))
async def ts_period_detail(callback: CallbackQuery, **kwargs) -> None:
    period_id = int(callback.data.split("_")[-1])
    session: AsyncSession = kwargs["db_session"]
    ts_service = TimesheetService(session)
    status = await ts_service.get_submission_status(period_id)
    if not status:
        await callback.answer("Период не найден.")
        return
    period = status["period"]
    emp_label = "Штатные" if period.employee_type == EmployeeType.FULL_TIME else "Нештатные"
    text = (
        f"📊 <b>Период {period.start_date.strftime('%d.%m')}–{period.end_date.strftime('%d.%m')}</b>\n"
        f"Тип: {emp_label}\n"
        f"Дедлайн: {period.deadline.strftime('%d.%m.%Y')}\n\n"
        f"Сдали: {status['submitted']} из {status['total']}\n"
    )
    if status["missing"]:
        names = ", ".join(u.display_name for u in status["missing"])
        text += f"\nНе сдали: {names}"
    is_collecting = period.status == PeriodStatus.COLLECTING
    await callback.message.answer(text, parse_mode="HTML", reply_markup=get_period_detail_keyboard(period_id, is_collecting))
    await callback.answer()


# ── Выгрузить в Google ─────────────────────────────────────────────

@router.callback_query(F.data == "ts_export")
async def ts_export_menu(callback: CallbackQuery, **kwargs) -> None:
    session: AsyncSession = kwargs["db_session"]
    ts_service = TimesheetService(session)
    periods = await ts_service.get_all_periods()
    await callback.message.edit_text("📤 Выберите период для выгрузки:", reply_markup=get_export_periods_keyboard(periods))
    await callback.answer()


@router.callback_query(F.data.startswith("ts_doexport_"))
async def ts_do_export(callback: CallbackQuery, **kwargs) -> None:
    period_id = int(callback.data.split("_")[-1])
    session: AsyncSession = kwargs["db_session"]

    # Check Google settings
    ts_service = TimesheetService(session)
    settings = await ts_service.get_google_settings()
    if not settings["spreadsheet_id"] or not settings["credentials_json"]:
        await callback.answer("Сначала настройте Google (ссылка и JSON-ключ).", show_alert=True)
        return

    from services.google_sheets_service import GoogleSheetsService
    sheets_service = GoogleSheetsService(session)
    url = await sheets_service.export_period(period_id)

    if url:
        await callback.message.edit_text(f"✅ Выгружено в Google Таблицы!\n\n{url}")
    else:
        await callback.message.edit_text("❌ Ошибка выгрузки. Проверьте настройки Google.")
    await callback.answer()


# ── Настройки сотрудников ──────────────────────────────────────────

@router.callback_query(F.data == "ts_employees")
async def ts_employees_list(callback: CallbackQuery, **kwargs) -> None:
    session: AsyncSession = kwargs["db_session"]
    user_service = UserService(session)
    users = await user_service.get_all_users(limit=100)
    # Only show users (not operators/admins) or those with employee_type set
    await callback.message.edit_text("👤 Выберите сотрудника:", reply_markup=get_employees_keyboard(users))
    await callback.answer()


@router.callback_query(F.data.startswith("ts_emp_") and not F.data.startswith("ts_emptype_") and not F.data.startswith("ts_empwork_") and not F.data.startswith("ts_empname_"))
async def ts_employee_detail(callback: CallbackQuery, **kwargs) -> None:
    user_id = int(callback.data.split("_")[-1])
    session: AsyncSession = kwargs["db_session"]
    user_service = UserService(session)
    user = await user_service.get_by_id(user_id)
    if not user:
        await callback.answer("Пользователь не найден.")
        return
    emp_type = "Штатный" if user.employee_type and user.employee_type.value == "full_time" else (
        "Нештатный" if user.employee_type else "Не задан"
    )
    text = (
        f"👤 {user.display_name}\n\n"
        f"Тип сотрудника: {emp_type}\n"
        f"Место работы: {user.workplace or '—'}\n"
        f"ФИО для табеля: {user.full_name or '—'}\n"
        f"Собирает часы: {'Да' if user.collects_hours else 'Нет'}"
    )
    await callback.message.answer(text, reply_markup=get_employee_edit_keyboard(user_id))
    await callback.answer()


@router.callback_query(F.data.startswith("ts_emptype_"))
async def ts_set_employee_type(callback: CallbackQuery, **kwargs) -> None:
    user_id = int(callback.data.split("_")[-1])
    await callback.message.answer(
        "Выберите тип сотрудника:",
        reply_markup=get_employee_type_keyboard(f"ts_setemptype_{user_id}_"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("ts_setemptype_"))
async def ts_do_set_employee_type(callback: CallbackQuery, **kwargs) -> None:
    parts = callback.data.split("_")
    user_id = int(parts[-2])
    emp_type_str = parts[-1]
    session: AsyncSession = kwargs["db_session"]
    user_service = UserService(session)
    user = await user_service.get_by_id(user_id)
    if user:
        user.employee_type = EmployeeType(emp_type_str)
    await callback.message.edit_text(f"Тип сотрудника изменён на {'Штатный' if emp_type_str == 'full_time' else 'Нештатный'}.")
    await callback.answer()


@router.callback_query(F.data.startswith("ts_empwork_"))
async def ts_set_workplace(callback: CallbackQuery, state: FSMContext, **kwargs) -> None:
    user_id = int(callback.data.split("_")[-1])
    await state.set_state(TimesheetStates.entering_workplace)
    await state.update_data(edit_user_id=user_id)
    await callback.message.answer("Введите место работы (например: Склад, Офис):", reply_markup=get_cancel_keyboard())
    await callback.answer()


@router.message(TimesheetStates.entering_workplace)
async def ts_do_set_workplace(message: Message, state: FSMContext, **kwargs) -> None:
    if not message.text or len(message.text.strip()) < 2:
        await message.answer("Слишком короткое название.")
        return
    state_data = await state.get_data()
    user_id = state_data.get("edit_user_id")
    session: AsyncSession = kwargs["db_session"]
    user_service = UserService(session)
    user = await user_service.get_by_id(user_id)
    if user:
        user.workplace = message.text.strip()
    await state.clear()
    await message.answer(f"Место работы изменено на: {message.text.strip()}")


@router.callback_query(F.data.startswith("ts_empname_"))
async def ts_set_full_name(callback: CallbackQuery, state: FSMContext, **kwargs) -> None:
    user_id = int(callback.data.split("_")[-1])
    await state.set_state(TimesheetStates.entering_full_name)
    await state.update_data(edit_user_id=user_id)
    await callback.message.answer("Введите ФИО в формате: Фамилия Имя Отчество", reply_markup=get_cancel_keyboard())
    await callback.answer()


@router.message(TimesheetStates.entering_full_name)
async def ts_do_set_full_name(message: Message, state: FSMContext, **kwargs) -> None:
    if not message.text or len(message.text.strip()) < 5:
        await message.answer("ФИО слишком короткое. Формат: Фамилия Имя Отчество")
        return
    state_data = await state.get_data()
    user_id = state_data.get("edit_user_id")
    session: AsyncSession = kwargs["db_session"]
    user_service = UserService(session)
    user = await user_service.get_by_id(user_id)
    if user:
        user.full_name = message.text.strip()
    await state.clear()
    await message.answer(f"ФИО установлено: {message.text.strip()}")


# ── Google настройки ───────────────────────────────────────────────

@router.callback_query(F.data == "ts_google_settings")
async def ts_google_settings(callback: CallbackQuery, **kwargs) -> None:
    session: AsyncSession = kwargs["db_session"]
    ts_service = TimesheetService(session)
    settings = await ts_service.get_google_settings()
    has_id = "✅" if settings["spreadsheet_id"] else "❌"
    has_json = "✅" if settings["credentials_json"] else "❌"
    text = (
        f"⚙ <b>Google настройки</b>\n\n"
        f"Spreadsheet ID: {has_id}\n"
        f"JSON-ключ: {has_json}\n\n"
        f"Для настройки нужны:\n"
        f"1. ID Google Таблицы (из URL)\n"
        f"2. JSON-ключ Service Account"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Ввести Spreadsheet ID", callback_data="ts_set_spreadsheet")],
        [InlineKeyboardButton(text="🔑 Ввести JSON-ключ", callback_data="ts_set_json")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="ts_admin")],
    ])
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "ts_set_spreadsheet")
async def ts_set_spreadsheet(callback: CallbackQuery, state: FSMContext, **kwargs) -> None:
    await state.set_state(TimesheetStates.entering_spreadsheet_id)
    await callback.message.answer(
        "Введите Spreadsheet ID из URL таблицы.\n"
        "Пример: https://docs.google.com/spreadsheets/d/<b>ЭТО_ID</b>/edit",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard(),
    )
    await callback.answer()


@router.message(TimesheetStates.entering_spreadsheet_id)
async def ts_do_set_spreadsheet(message: Message, state: FSMContext, **kwargs) -> None:
    spreadsheet_id = message.text.strip().split("/")[-1] if "/" in message.text else message.text.strip()
    session: AsyncSession = kwargs["db_session"]
    ts_service = TimesheetService(session)
    await ts_service.set_google_settings(spreadsheet_id=spreadsheet_id, credentials_json="")
    await state.clear()
    await message.answer(f"✅ Spreadsheet ID сохранён: {spreadsheet_id}")


@router.callback_query(F.data == "ts_set_json")
async def ts_set_json(callback: CallbackQuery, state: FSMContext, **kwargs) -> None:
    await state.set_state(TimesheetStates.entering_credentials_json)
    await callback.message.answer(
        "Вставьте JSON-ключ Service Account (одним сообщением):",
        reply_markup=get_cancel_keyboard(),
    )
    await callback.answer()


@router.message(TimesheetStates.entering_credentials_json)
async def ts_do_set_json(message: Message, state: FSMContext, **kwargs) -> None:
    import json
    json_text = message.text.strip()
    try:
        json.loads(json_text)  # Validate JSON
    except json.JSONDecodeError:
        await message.answer("❌ Неверный JSON. Попробуйте ещё раз.")
        return
    session: AsyncSession = kwargs["db_session"]
    ts_service = TimesheetService(session)
    settings = await ts_service.get_google_settings()
    await ts_service.set_google_settings(spreadsheet_id=settings["spreadsheet_id"], credentials_json=json_text)
    await state.clear()
    await message.answer("✅ JSON-ключ сохранён.")


# ── Вспомогательные ───────────────────────────────────────────────

async def _notify_if_period_complete(period_id: int, kwargs: dict) -> None:
    """Check if period is complete and notify the responsible operator."""
    session: AsyncSession = kwargs["db_session"]
    ts_service = TimesheetService(session)
    status = await ts_service.get_submission_status(period_id)
    if not status or status.get("submitted", 0) < status.get("total", 0):
        return
    period = status.get("period")
    if not period:
        return
    # Mark as completed
    await ts_service.mark_completed(period_id)
    # Notify responsible operator
    bot: Bot = kwargs["bot"]
    if period.responsible_operator_id:
        try:
            await bot.send_message(
                period.responsible_operator_id,
                f"✅ Часы собраны за период {period.start_date.strftime('%d.%m')}–{period.end_date.strftime('%d.%m')}!\n\n"
                f"Все сотрудники сдали часы. Можно выгрузить в Google Таблицу.",
            )
        except Exception:
            pass


def _get_main_menu_by_role(role: RoleEnum):
    from bot.keyboards.common import get_main_menu_admin, get_main_menu_operator, get_main_menu_user
    if role == RoleEnum.ADMIN:
        return get_main_menu_admin
    elif role == RoleEnum.OPERATOR:
        return get_main_menu_operator
    else:
        return get_main_menu_user


# Import for inline keyboard in ts_google_settings
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
