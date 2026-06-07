from __future__ import annotations

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.role import RoleEnum
from database.models.user import User
from services.user_service import UserService
from services.faq_service import FAQService
from services.auto_answer_service import AutoAnswerService
from services.statistics_service import StatisticsService
from services.export_service import ExportService
from services.audit_service import AuditService
from bot.states.faq_states import FAQManagement
from bot.states.auto_answer_states import AutoAnswerManagement
from bot.keyboards.common import (
    get_main_menu_admin,
    get_cancel_keyboard,
    get_admin_management_menu,
    get_admin_tickets_menu,
    get_admin_settings_menu,
)
from bot.keyboards.admin import (
    get_users_keyboard,
    get_faq_management_keyboard,
    get_auto_answer_management_keyboard,
    get_admin_faq_list_keyboard,
    get_faq_detail_keyboard,
    get_auto_answer_list_keyboard,
    get_auto_answer_detail_keyboard,
    get_role_change_keyboard,
    get_db_cleanup_keyboard,
    get_db_cleanup_confirm_keyboard,
)
from bot.states.category_management_states import CategoryManagement
from database.repositories.category_repo import CategoryRepository
from utils.permissions import is_admin
import tempfile
import os


router = Router()


# ── Проверка прав администратора ───────────────────────────────────

def _is_admin(**kwargs) -> bool:
    """Check admin role from middleware-injected data."""
    user_role: RoleEnum | None = kwargs.get("user_role")
    return user_role is not None and is_admin(user_role)


async def _check_admin_and_reply(event, **kwargs) -> bool:
    """Check admin + send error message + log unauthorized access."""
    if _is_admin(**kwargs):
        return True

    session: AsyncSession | None = kwargs.get("db_session")
    if isinstance(event, CallbackQuery):
        await event.answer(
            "Недостаточно прав для выполнения действия.", show_alert=True
        )
        if session:
            audit_service = AuditService(session)
            await audit_service.log_unauthorized_access(
                user_id=event.from_user.id,
                role=None,
                action=event.data or "admin_action",
            )
    else:
        await event.answer("Недостаточно прав для выполнения действия.")
    return False


# ── Подменю админа ─────────────────────────────────────────────────

@router.message(F.text == "🛠 Управление")
async def admin_management_menu(message: Message, **kwargs) -> None:
    if not _is_admin(**kwargs):
        await message.answer("Недостаточно прав.")
        return
    await message.answer("🛠 <b>Управление</b>", parse_mode="HTML",
                         reply_markup=get_admin_management_menu())


@router.message(F.text == "📋 Обращения")
async def admin_tickets_menu(message: Message, **kwargs) -> None:
    if not _is_admin(**kwargs):
        await message.answer("Недостаточно прав.")
        return
    await message.answer("📋 <b>Обращения</b>", parse_mode="HTML",
                         reply_markup=get_admin_tickets_menu())


@router.message(F.text == "⚙ Настройки")
async def admin_settings_menu(message: Message, **kwargs) -> None:
    if not _is_admin(**kwargs):
        await message.answer("Недостаточно прав.")
        return
    await message.answer("⚙ <b>Настройки</b>", parse_mode="HTML",
                         reply_markup=get_admin_settings_menu())


@router.message(F.text == "🔙 В меню")
async def admin_back_to_menu(message: Message, state: FSMContext, **kwargs) -> None:
    await state.clear()
    user_role: RoleEnum | None = kwargs.get("user_role")
    if user_role == RoleEnum.ADMIN:
        await message.answer("👑 Главное меню", reply_markup=get_main_menu_admin())
    else:
        from bot.keyboards.common import get_main_menu_by_role
        await message.answer("Главное меню", reply_markup=get_main_menu_by_role(user_role))


@router.message(F.text == "🔧 Настройки бота")
async def admin_bot_settings(message: Message, **kwargs) -> None:
    if not _is_admin(**kwargs):
        await message.answer("Недостаточно прав.")
        return
    session: AsyncSession = kwargs["db_session"]
    audit_service = AuditService(session)
    await audit_service.log(
        user_id=message.from_user.id, role="admin",
        action="enter_settings", object_type="system",
    )
    await message.answer(
        "🔧 <b>Настройки бота</b>\n\n"
        "Для настройки Google Sheets перейдите в 🕐 Табель → ⚙ Google настройки.",
        parse_mode="HTML",
    )


@router.message(F.text == "🧹 Очистка данных")
async def admin_cleanup_menu(message: Message, **kwargs) -> None:
    if not _is_admin(**kwargs):
        await message.answer("Недостаточно прав.")
        return
    session: AsyncSession = kwargs["db_session"]

    from sqlalchemy import text as sa_text
    from bot.keyboards.admin import get_db_cleanup_keyboard

    _MODEL_TO_TABLE = {
        "tickets": "tickets", "ticket_messages": "ticket_messages",
        "ratings": "ratings", "timesheet_periods": "timesheet_periods",
        "timesheet_entries": "timesheet_entries", "faqs": "faqs",
        "auto_answers": "auto_answers", "quick_replies": "quick_replies",
        "audit_logs": "audit_logs", "bot_settings": "bot_settings",
    }
    counts = {}
    for model_name, table_name in _MODEL_TO_TABLE.items():
        try:
            result = await session.execute(sa_text(f"SELECT COUNT(*) FROM {table_name}"))
            counts[model_name] = result.scalar_one()
        except Exception:
            counts[model_name] = "?"

    await message.answer(
        "🧹 <b>Очистка данных</b>\n\n"
        "Выберите, что очистить. Пользователи и категории не удаляются.\n\n"
        f"• Тикеты + сообщения: {counts.get('tickets', '?')} / {counts.get('ticket_messages', '?')}\n"
        f"• Оценки: {counts.get('ratings', '?')}\n"
        f"• Табели: {counts.get('timesheet_periods', '?')} / {counts.get('timesheet_entries', '?')}\n"
        f"• FAQ: {counts.get('faqs', '?')}\n"
        f"• Автоответы: {counts.get('auto_answers', '?')}\n"
        f"• Быстрые ответы: {counts.get('quick_replies', '?')}\n"
        f"• Аудит: {counts.get('audit_logs', '?')}\n"
        f"• Настройки бота: {counts.get('bot_settings', '?')}",
        parse_mode="HTML",
        reply_markup=get_db_cleanup_keyboard(),
    )


# ── Пользователи ───────────────────────────────────────────────────

@router.message(F.text == "👥 Пользователи")
async def show_users(message: Message, **kwargs) -> None:
    if not _is_admin(**kwargs):
        await message.answer("Недостаточно прав для выполнения действия.")
        return

    session: AsyncSession = kwargs["db_session"]
    user_service = UserService(session)
    users = await user_service.get_all_users(limit=10, offset=0)
    total = await user_service.count_users()

    if not users:
        await message.answer("Пользователи не найдены.")
        return

    await message.answer(
        "👥 Список пользователей:",
        reply_markup=get_users_keyboard(users, total=total),
    )


@router.callback_query(F.data.startswith("users_page_"))
async def users_page(callback: CallbackQuery, **kwargs) -> None:
    if not await _check_admin_and_reply(callback, **kwargs):
        return

    page = int(callback.data.split("_")[-1])
    per_page = 10

    session: AsyncSession = kwargs["db_session"]
    user_service = UserService(session)
    users = await user_service.get_all_users(limit=per_page, offset=page * per_page)
    total = await user_service.count_users()

    await callback.message.edit_text(
        "👥 Список пользователей:",
        reply_markup=get_users_keyboard(users, page=page, total=total),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_user_"))
async def admin_view_user(callback: CallbackQuery, **kwargs) -> None:
    if not await _check_admin_and_reply(callback, **kwargs):
        return

    user_id = int(callback.data.split("_")[-1])

    session: AsyncSession = kwargs["db_session"]
    user_service = UserService(session)
    user = await user_service.get_by_id(user_id)

    if not user:
        await callback.answer("Пользователь не найден.")
        return

    role_name = user.role.name.value if user.role and hasattr(user.role.name, "value") else "—"
    role_display = {"admin": "👑 Админ", "operator": "🛠 Оператор", "user": "👤 Пользователь"}.get(role_name, role_name)

    text = (
        f"👤 <b>Пользователь</b>\n\n"
        f"Имя: {user.display_name}\n"
        f"Telegram ID: <code>{user.telegram_id}</code>\n"
        f"Телефон: {user.phone or '—'}\n"
        f"Роль: {role_display}\n"
        f"Дата регистрации: {user.registered_at.strftime('%d.%m.%Y %H:%M') if user.registered_at else '—'}\n"
    )

    await callback.message.answer(
        text,
        parse_mode="HTML",
        reply_markup=get_role_change_keyboard(user.id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("set_role_"))
async def set_role(callback: CallbackQuery, **kwargs) -> None:
    if not await _check_admin_and_reply(callback, **kwargs):
        return

    parts = callback.data.split("_")
    # set_role_{user_id}_{role}
    user_id = int(parts[2])
    role_str = parts[3]

    role_map = {
        "user": RoleEnum.USER,
        "operator": RoleEnum.OPERATOR,
        "admin": RoleEnum.ADMIN,
    }
    new_role = role_map.get(role_str)
    if not new_role:
        await callback.answer("Неизвестная роль.")
        return

    session: AsyncSession = kwargs["db_session"]
    user_service = UserService(session)
    user = await user_service.change_role(
        admin_telegram_id=callback.from_user.id,
        target_user_id=user_id,
        new_role=new_role,
    )

    if not user:
        await callback.answer("Пользователь не найден.", show_alert=True)
        return

    role_display = {"admin": "👑 Админ", "operator": "🛠 Оператор", "user": "👤 Пользователь"}.get(role_str, role_str)

    await callback.message.edit_text(
        f"Роль пользователя {user.display_name} изменена на {role_display}."
    )
    await callback.answer("Роль обновлена!")


@router.callback_query(F.data == "back_to_users")
async def back_to_users(callback: CallbackQuery, **kwargs) -> None:
    if not await _check_admin_and_reply(callback, **kwargs):
        return

    session: AsyncSession = kwargs["db_session"]
    user_service = UserService(session)
    users = await user_service.get_all_users(limit=10, offset=0)
    total = await user_service.count_users()

    await callback.message.edit_text(
        "👥 Список пользователей:",
        reply_markup=get_users_keyboard(users, total=total),
    )
    await callback.answer()


# ── FAQ Management ─────────────────────────────────────────────────

@router.message(F.text == "📚 Управление FAQ")
async def admin_faq_menu(message: Message, **kwargs) -> None:
    if not _is_admin(**kwargs):
        await message.answer("Недостаточно прав для выполнения действия.")
        return

    await message.answer(
        "📚 Управление FAQ:",
        reply_markup=get_faq_management_keyboard(),
    )


@router.callback_query(F.data == "admin_faq_menu")
async def admin_faq_menu_callback(callback: CallbackQuery, **kwargs) -> None:
    if not await _check_admin_and_reply(callback, **kwargs):
        return

    await callback.message.edit_text(
        "📚 Управление FAQ:",
        reply_markup=get_faq_management_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin_faq_list")
async def admin_faq_list(callback: CallbackQuery, **kwargs) -> None:
    if not await _check_admin_and_reply(callback, **kwargs):
        return

    session: AsyncSession = kwargs["db_session"]
    faq_service = FAQService(session)
    faqs = await faq_service.get_all()

    if not faqs:
        await callback.message.edit_text("FAQ пуст.", reply_markup=None)
        await callback.answer()
        return

    await callback.message.edit_text(
        "📋 Список FAQ:",
        reply_markup=get_admin_faq_list_keyboard(faqs),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_faq_") & ~F.data.startswith("admin_faq_menu") & ~F.data.startswith("admin_faq_list") & ~F.data.startswith("admin_faq_add") & ~F.data.startswith("admin_faq_edit") & ~F.data.startswith("admin_faq_toggle") & ~F.data.startswith("admin_faq_del"))
async def admin_faq_detail(callback: CallbackQuery, **kwargs) -> None:
    if not await _check_admin_and_reply(callback, **kwargs):
        return

    faq_id = int(callback.data.split("_")[-1])

    session: AsyncSession = kwargs["db_session"]
    faq_service = FAQService(session)
    faq = await faq_service.get_by_id(faq_id)

    if not faq:
        await callback.answer("FAQ не найден.")
        return

    text = (
        f"❓ <b>Вопрос:</b>\n{faq.question}\n\n"
        f"💬 <b>Ответ:</b>\n{faq.answer}\n\n"
        f"Статус: {'✅ Активен' if faq.is_active else '❌ Отключен'}"
    )

    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_faq_detail_keyboard(faq.id, faq.is_active),
    )
    await callback.answer()


@router.callback_query(F.data == "admin_faq_add")
async def admin_faq_add(callback: CallbackQuery, state: FSMContext, **kwargs) -> None:
    if not await _check_admin_and_reply(callback, **kwargs):
        return

    await state.set_state(FAQManagement.waiting_question)
    await callback.message.answer(
        "Введите вопрос для FAQ:",
        reply_markup=get_cancel_keyboard(),
    )
    await callback.answer()


@router.message(FAQManagement.waiting_question, F.text == "❌ Отмена")
async def cancel_faq_add(message: Message, state: FSMContext, **kwargs) -> None:
    await state.clear()
    await message.answer("Добавление FAQ отменено.", reply_markup=get_main_menu_admin())


@router.message(FAQManagement.waiting_question)
async def faq_enter_question(message: Message, state: FSMContext, **kwargs) -> None:
    if not message.text or len(message.text.strip()) < 3:
        await message.answer("Вопрос слишком короткий. Попробуйте ещё раз.")
        return

    await state.update_data(question=message.text.strip())
    await state.set_state(FAQManagement.waiting_answer)
    await message.answer("Введите ответ для FAQ:")


@router.message(FAQManagement.waiting_answer)
async def faq_enter_answer(message: Message, state: FSMContext, **kwargs) -> None:
    if not message.text or len(message.text.strip()) < 3:
        await message.answer("Ответ слишком короткий. Попробуйте ещё раз.")
        return

    state_data = await state.get_data()
    question = state_data.get("question")

    session: AsyncSession = kwargs["db_session"]
    faq_service = FAQService(session)
    await faq_service.create(
        admin_id=message.from_user.id,
        question=question,
        answer=message.text.strip(),
    )

    await state.clear()
    await message.answer(
        "FAQ добавлен!",
        reply_markup=get_main_menu_admin(),
    )


@router.callback_query(F.data.startswith("admin_faq_toggle_"))
async def admin_faq_toggle(callback: CallbackQuery, **kwargs) -> None:
    if not await _check_admin_and_reply(callback, **kwargs):
        return

    faq_id = int(callback.data.split("_")[-1])

    session: AsyncSession = kwargs["db_session"]
    faq_service = FAQService(session)
    faq = await faq_service.toggle_active(callback.from_user.id, faq_id)

    if not faq:
        await callback.answer("FAQ не найден.")
        return

    status = "включен" if faq.is_active else "отключен"
    await callback.answer(f"FAQ {status}!")


@router.callback_query(F.data.startswith("admin_faq_del_"))
async def admin_faq_delete(callback: CallbackQuery, **kwargs) -> None:
    if not await _check_admin_and_reply(callback, **kwargs):
        return

    faq_id = int(callback.data.split("_")[-1])

    session: AsyncSession = kwargs["db_session"]
    faq_service = FAQService(session)
    deleted = await faq_service.delete(callback.from_user.id, faq_id)

    if deleted:
        await callback.message.edit_text("FAQ удалён.")
    else:
        await callback.answer("FAQ не найден.")
    await callback.answer()


@router.callback_query(F.data.startswith("admin_faq_edit_"))
async def admin_faq_edit(callback: CallbackQuery, state: FSMContext, **kwargs) -> None:
    if not await _check_admin_and_reply(callback, **kwargs):
        return

    faq_id = int(callback.data.split("_")[-1])

    session: AsyncSession = kwargs["db_session"]
    faq_service = FAQService(session)
    faq = await faq_service.get_by_id(faq_id)

    if not faq:
        await callback.answer("FAQ не найден.")
        return

    await state.update_data(faq_id=faq_id)
    await state.set_state(FAQManagement.waiting_edit_question)
    await callback.message.answer(
        f"Текущий вопрос:\n{faq.question}\n\nВведите новый вопрос (или отправьте '-' чтобы оставить текущий):",
        reply_markup=get_cancel_keyboard(),
    )
    await callback.answer()


@router.message(FAQManagement.waiting_edit_question, F.text == "❌ Отмена")
async def cancel_faq_edit(message: Message, state: FSMContext, **kwargs) -> None:
    await state.clear()
    await message.answer("Редактирование FAQ отменено.", reply_markup=get_main_menu_admin())


@router.message(FAQManagement.waiting_edit_question)
async def faq_edit_question(message: Message, state: FSMContext, **kwargs) -> None:
    question = None if (message.text and message.text.strip() == "-") else message.text.strip()
    await state.update_data(new_question=question)
    await state.set_state(FAQManagement.waiting_edit_answer)

    state_data = await state.get_data()
    session: AsyncSession = kwargs["db_session"]
    faq_service = FAQService(session)
    faq = await faq_service.get_by_id(state_data["faq_id"])

    await message.answer(
        f"Текущий ответ:\n{faq.answer}\n\nВведите новый ответ (или отправьте '-' чтобы оставить текущий):",
    )


@router.message(FAQManagement.waiting_edit_answer)
async def faq_edit_answer(message: Message, state: FSMContext, **kwargs) -> None:
    answer = None if (message.text and message.text.strip() == "-") else message.text.strip()
    state_data = await state.get_data()
    faq_id = state_data.get("faq_id")
    new_question = state_data.get("new_question")

    session: AsyncSession = kwargs["db_session"]
    faq_service = FAQService(session)
    await faq_service.update(
        admin_id=message.from_user.id,
        faq_id=faq_id,
        question=new_question,
        answer=answer,
    )

    await state.clear()
    await message.answer("FAQ обновлён!", reply_markup=get_main_menu_admin())


# ── Автоответы Management ──────────────────────────────────────────

@router.message(F.text == "🤖 Автоответы")
async def admin_auto_answer_menu(message: Message, **kwargs) -> None:
    if not _is_admin(**kwargs):
        await message.answer("Недостаточно прав для выполнения действия.")
        return

    await message.answer(
        "🤖 Управление автоответами:",
        reply_markup=get_auto_answer_management_keyboard(),
    )


@router.callback_query(F.data == "admin_aa_menu")
async def admin_aa_menu_callback(callback: CallbackQuery, **kwargs) -> None:
    if not await _check_admin_and_reply(callback, **kwargs):
        return

    await callback.message.edit_text(
        "🤖 Управление автоответами:",
        reply_markup=get_auto_answer_management_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin_aa_list")
async def admin_aa_list(callback: CallbackQuery, **kwargs) -> None:
    if not await _check_admin_and_reply(callback, **kwargs):
        return

    session: AsyncSession = kwargs["db_session"]
    aa_service = AutoAnswerService(session)
    auto_answers = await aa_service.get_all()

    if not auto_answers:
        await callback.message.edit_text("Список автоответов пуст.", reply_markup=None)
        await callback.answer()
        return

    await callback.message.edit_text(
        "📋 Список автоответов:",
        reply_markup=get_auto_answer_list_keyboard(auto_answers),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_aa_") & ~F.data.startswith("admin_aa_menu") & ~F.data.startswith("admin_aa_list") & ~F.data.startswith("admin_aa_add") & ~F.data.startswith("admin_aa_edit") & ~F.data.startswith("admin_aa_toggle") & ~F.data.startswith("admin_aa_del"))
async def admin_aa_detail(callback: CallbackQuery, **kwargs) -> None:
    if not await _check_admin_and_reply(callback, **kwargs):
        return

    aa_id = int(callback.data.split("_")[-1])

    session: AsyncSession = kwargs["db_session"]
    aa_service = AutoAnswerService(session)
    aa = await aa_service.get_by_id(aa_id)

    if not aa:
        await callback.answer("Автоответ не найден.")
        return

    text = (
        f"🔑 <b>Ключевые слова:</b>\n{aa.keywords}\n\n"
        f"💬 <b>Ответ:</b>\n{aa.answer}\n\n"
        f"Статус: {'✅ Активен' if aa.is_active else '❌ Отключен'}"
    )

    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_auto_answer_detail_keyboard(aa.id, aa.is_active),
    )
    await callback.answer()


@router.callback_query(F.data == "admin_aa_add")
async def admin_aa_add(callback: CallbackQuery, state: FSMContext, **kwargs) -> None:
    if not await _check_admin_and_reply(callback, **kwargs):
        return

    await state.set_state(AutoAnswerManagement.waiting_keywords)
    await callback.message.answer(
        "Введите ключевые слова через запятую\n(например: зарплата,зп,когда зарплата):",
        reply_markup=get_cancel_keyboard(),
    )
    await callback.answer()


@router.message(AutoAnswerManagement.waiting_keywords, F.text == "❌ Отмена")
async def cancel_aa_add(message: Message, state: FSMContext, **kwargs) -> None:
    await state.clear()
    await message.answer("Добавление автоответа отменено.", reply_markup=get_main_menu_admin())


@router.message(AutoAnswerManagement.waiting_keywords)
async def aa_enter_keywords(message: Message, state: FSMContext, **kwargs) -> None:
    if not message.text or len(message.text.strip()) < 2:
        await message.answer("Ключевые слова слишком короткие. Попробуйте ещё раз.")
        return

    await state.update_data(keywords=message.text.strip())
    await state.set_state(AutoAnswerManagement.waiting_answer)
    await message.answer("Введите текст автоответа:")


@router.message(AutoAnswerManagement.waiting_answer)
async def aa_enter_answer(message: Message, state: FSMContext, **kwargs) -> None:
    if not message.text or len(message.text.strip()) < 3:
        await message.answer("Ответ слишком короткий. Попробуйте ещё раз.")
        return

    state_data = await state.get_data()
    keywords = state_data.get("keywords")

    session: AsyncSession = kwargs["db_session"]
    aa_service = AutoAnswerService(session)
    await aa_service.create(
        admin_id=message.from_user.id,
        keywords=keywords,
        answer=message.text.strip(),
    )

    await state.clear()
    await message.answer(
        "Автоответ добавлен!",
        reply_markup=get_main_menu_admin(),
    )


@router.callback_query(F.data.startswith("admin_aa_toggle_"))
async def admin_aa_toggle(callback: CallbackQuery, **kwargs) -> None:
    if not await _check_admin_and_reply(callback, **kwargs):
        return

    aa_id = int(callback.data.split("_")[-1])

    session: AsyncSession = kwargs["db_session"]
    aa_service = AutoAnswerService(session)
    aa = await aa_service.toggle_active(callback.from_user.id, aa_id)

    if not aa:
        await callback.answer("Автоответ не найден.")
        return

    status = "включен" if aa.is_active else "отключен"
    await callback.answer(f"Автоответ {status}!")


@router.callback_query(F.data.startswith("admin_aa_del_"))
async def admin_aa_delete(callback: CallbackQuery, **kwargs) -> None:
    if not await _check_admin_and_reply(callback, **kwargs):
        return

    aa_id = int(callback.data.split("_")[-1])

    session: AsyncSession = kwargs["db_session"]
    aa_service = AutoAnswerService(session)
    deleted = await aa_service.delete(callback.from_user.id, aa_id)

    if deleted:
        await callback.message.edit_text("Автоответ удалён.")
    else:
        await callback.answer("Автоответ не найден.")
    await callback.answer()


@router.callback_query(F.data.startswith("admin_aa_edit_"))
async def admin_aa_edit(callback: CallbackQuery, state: FSMContext, **kwargs) -> None:
    if not await _check_admin_and_reply(callback, **kwargs):
        return

    aa_id = int(callback.data.split("_")[-1])

    session: AsyncSession = kwargs["db_session"]
    aa_service = AutoAnswerService(session)
    aa = await aa_service.get_by_id(aa_id)

    if not aa:
        await callback.answer("Автоответ не найден.")
        return

    await state.update_data(aa_id=aa_id)
    await state.set_state(AutoAnswerManagement.waiting_edit_keywords)
    await callback.message.answer(
        f"Текущие ключевые слова:\n{aa.keywords}\n\nВведите новые ключевые слова (или '-' чтобы оставить текущие):",
        reply_markup=get_cancel_keyboard(),
    )
    await callback.answer()


@router.message(AutoAnswerManagement.waiting_edit_keywords, F.text == "❌ Отмена")
async def cancel_aa_edit(message: Message, state: FSMContext, **kwargs) -> None:
    await state.clear()
    await message.answer("Редактирование автоответа отменено.", reply_markup=get_main_menu_admin())


@router.message(AutoAnswerManagement.waiting_edit_keywords)
async def aa_edit_keywords(message: Message, state: FSMContext, **kwargs) -> None:
    keywords = None if (message.text and message.text.strip() == "-") else message.text.strip()
    await state.update_data(new_keywords=keywords)
    await state.set_state(AutoAnswerManagement.waiting_edit_answer)

    state_data = await state.get_data()
    session: AsyncSession = kwargs["db_session"]
    aa_service = AutoAnswerService(session)
    aa = await aa_service.get_by_id(state_data["aa_id"])

    await message.answer(
        f"Текущий ответ:\n{aa.answer}\n\nВведите новый ответ (или '-' чтобы оставить текущий):",
    )


@router.message(AutoAnswerManagement.waiting_edit_answer)
async def aa_edit_answer(message: Message, state: FSMContext, **kwargs) -> None:
    answer = None if (message.text and message.text.strip() == "-") else message.text.strip()
    state_data = await state.get_data()
    aa_id = state_data.get("aa_id")
    new_keywords = state_data.get("new_keywords")

    session: AsyncSession = kwargs["db_session"]
    aa_service = AutoAnswerService(session)
    await aa_service.update(
        admin_id=message.from_user.id,
        auto_answer_id=aa_id,
        keywords=new_keywords,
        answer=answer,
    )

    await state.clear()
    await message.answer("Автоответ обновлён!", reply_markup=get_main_menu_admin())


# ── Статистика ─────────────────────────────────────────────────────

@router.message(F.text == "📊 Статистика")
async def show_statistics(message: Message, **kwargs) -> None:
    if not _is_admin(**kwargs):
        await message.answer("Недостаточно прав для выполнения действия.")
        return

    session: AsyncSession = kwargs["db_session"]
    stats_service = StatisticsService(session)
    stats = await stats_service.get_statistics()

    text = (
        "📊 <b>Статистика системы</b>\n\n"
        f"👥 Пользователей: {stats['total_users']}\n"
        f"🛠 Операторов: {stats['total_operators']}\n"
        f"📨 Всего обращений: {stats['total_tickets']}\n"
        f"📂 Открытых тикетов: {stats['open_tickets']}\n"
        f"✅ Закрытых тикетов: {stats['closed_tickets']}\n"
        f"⭐ Средняя оценка: {stats['average_score']}\n"
    )

    if stats["by_category"]:
        text += "\n📁 <b>По категориям:</b>\n"
        for cat_name, count in stats["by_category"].items():
            text += f"  • {cat_name}: {count}\n"

    await message.answer(text, parse_mode="HTML")


# ── Выгрузка ───────────────────────────────────────────────────────

@router.message(F.text == "📤 Выгрузка")
async def export_data(message: Message, **kwargs) -> None:
    if not _is_admin(**kwargs):
        await message.answer("Недостаточно прав для выполнения действия.")
        return

    await message.answer("Выполняется выгрузка данных...")

    session: AsyncSession = kwargs["db_session"]
    export_service = ExportService(session)
    buffer = await export_service.export_tickets_to_excel(message.from_user.id)

    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp.write(buffer.getvalue())
        tmp_path = tmp.name

    try:
        doc = FSInputFile(tmp_path, filename="helpdesk_tickets.xlsx")
        await message.answer_document(doc, caption="📊 Выгрузка обращений")
    finally:
        os.unlink(tmp_path)


# ── Управление категориями ────────────────────────────────────────

@router.message(F.text == "📁 Категории")
async def show_categories_menu(message: Message, **kwargs) -> None:
    if not _is_admin(**kwargs):
        await message.answer("Недостаточно прав.")
        return
    session: AsyncSession = kwargs["db_session"]
    cat_repo = CategoryRepository(session)
    categories = await cat_repo.get_roots()
    if not categories:
        await message.answer("Категории не созданы. Добавьте первую.")
        return
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    buttons = []
    for cat in categories:
        buttons.append([InlineKeyboardButton(text=cat.full_name, callback_data=f"cat_manage_{cat.id}")])
    buttons.append([InlineKeyboardButton(text="➕ Добавить категорию", callback_data="cat_add_root")])
    buttons.append([InlineKeyboardButton(text="🔙 В меню", callback_data="back_to_menu")])
    await message.answer("📁 Управление категориями:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))


@router.callback_query(F.data.startswith("cat_manage_"))
async def manage_category(callback: CallbackQuery, **kwargs) -> None:
    if not await _check_admin_and_reply(callback, **kwargs):
        return
    cat_id = int(callback.data.split("_")[-1])
    session: AsyncSession = kwargs["db_session"]
    cat_repo = CategoryRepository(session)
    cat = await cat_repo.get_by_id(cat_id)
    if not cat:
        await callback.answer("Категория не найдена.")
        return
    topics = await cat_repo.get_topics(cat_id)
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    buttons = []
    for topic in topics:
        buttons.append([InlineKeyboardButton(text=topic.full_name, callback_data=f"cat_manage_{topic.id}")])
    buttons.append([InlineKeyboardButton(text="➕ Добавить тему", callback_data=f"cat_add_topic_{cat_id}")])
    buttons.append([InlineKeyboardButton(text="✏ Переименовать", callback_data=f"cat_rename_{cat_id}")])
    buttons.append([InlineKeyboardButton(text="🗑 Удалить", callback_data=f"cat_delete_{cat_id}")])
    buttons.append([InlineKeyboardButton(text="🔙 К списку", callback_data="cat_list")])
    await callback.message.edit_text(
        f"📁 {cat.full_name}\n\nТем: {len(topics)}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )
    await callback.answer()


@router.callback_query(F.data == "cat_list")
async def cat_list(callback: CallbackQuery, **kwargs) -> None:
    session: AsyncSession = kwargs["db_session"]
    cat_repo = CategoryRepository(session)
    categories = await cat_repo.get_roots()
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    buttons = []
    for cat in categories:
        buttons.append([InlineKeyboardButton(text=cat.full_name, callback_data=f"cat_manage_{cat.id}")])
    buttons.append([InlineKeyboardButton(text="➕ Добавить категорию", callback_data="cat_add_root")])
    buttons.append([InlineKeyboardButton(text="🔙 В меню", callback_data="back_to_menu")])
    await callback.message.edit_text("📁 Управление категориями:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await callback.answer()


@router.callback_query(F.data == "cat_add_root")
async def cat_add_root(callback: CallbackQuery, state: FSMContext, **kwargs) -> None:
    if not await _check_admin_and_reply(callback, **kwargs):
        return
    await state.set_state(CategoryManagement.waiting_category_name)
    await state.update_data(parent_id=None)
    await callback.message.answer("Введите название новой категории:", reply_markup=get_cancel_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("cat_add_topic_"))
async def cat_add_topic(callback: CallbackQuery, state: FSMContext, **kwargs) -> None:
    if not await _check_admin_and_reply(callback, **kwargs):
        return
    parent_id = int(callback.data.split("_")[-1])
    await state.set_state(CategoryManagement.waiting_category_name)
    await state.update_data(parent_id=parent_id)
    await callback.message.answer("Введите название новой темы:", reply_markup=get_cancel_keyboard())
    await callback.answer()


@router.message(CategoryManagement.waiting_category_name, F.text == "❌ Отмена")
async def cancel_cat_add(message: Message, state: FSMContext, **kwargs) -> None:
    await state.clear()
    await message.answer("Отменено.", reply_markup=get_main_menu_admin())


@router.message(CategoryManagement.waiting_category_name)
async def enter_cat_name(message: Message, state: FSMContext, **kwargs) -> None:
    if not message.text or len(message.text.strip()) < 2:
        await message.answer("Название слишком короткое.")
        return
    state_data = await state.get_data()
    parent_id = state_data.get("parent_id")
    session: AsyncSession = kwargs["db_session"]
    cat_repo = CategoryRepository(session)
    await cat_repo.create(name=message.text.strip(), parent_id=parent_id)
    await state.clear()
    label = "Тема" if parent_id else "Категория"
    await message.answer(f"✅ {label} «{message.text.strip()}» добавлена!", reply_markup=get_main_menu_admin())


@router.callback_query(F.data.startswith("cat_rename_"))
async def cat_rename(callback: CallbackQuery, state: FSMContext, **kwargs) -> None:
    if not await _check_admin_and_reply(callback, **kwargs):
        return
    cat_id = int(callback.data.split("_")[-1])
    await state.set_state(CategoryManagement.waiting_edit_name)
    await state.update_data(cat_id=cat_id)
    session: AsyncSession = kwargs["db_session"]
    cat_repo = CategoryRepository(session)
    cat = await cat_repo.get_by_id(cat_id)
    await callback.message.answer(
        f"Текущее название: {cat.full_name}\n\nВведите новое название:",
        reply_markup=get_cancel_keyboard(),
    )
    await callback.answer()


@router.message(CategoryManagement.waiting_edit_name)
async def enter_new_cat_name(message: Message, state: FSMContext, **kwargs) -> None:
    if not message.text or len(message.text.strip()) < 2:
        await message.answer("Название слишком короткое.")
        return
    state_data = await state.get_data()
    cat_id = state_data.get("cat_id")
    session: AsyncSession = kwargs["db_session"]
    cat_repo = CategoryRepository(session)
    await cat_repo.update_name(cat_id, message.text.strip())
    await state.clear()
    await message.answer(f"✅ Название изменено на «{message.text.strip()}»", reply_markup=get_main_menu_admin())


@router.callback_query(F.data.startswith("cat_delete_"))
async def cat_delete(callback: CallbackQuery, **kwargs) -> None:
    if not await _check_admin_and_reply(callback, **kwargs):
        return
    cat_id = int(callback.data.split("_")[-1])
    session: AsyncSession = kwargs["db_session"]
    cat_repo = CategoryRepository(session)
    deleted = await cat_repo.delete(cat_id)
    if deleted:
        await callback.message.edit_text("✅ Категория удалена.")
    else:
        await callback.answer("Нельзя удалить: есть связанные тикеты.", show_alert=True)
    await callback.answer()


# ── Собирает часы (флаг для оператора) ─────────────────────────────

@router.callback_query(F.data.startswith("set_hours_collector_"))
async def set_hours_collector(callback: CallbackQuery, **kwargs) -> None:
    if not await _check_admin_and_reply(callback, **kwargs):
        return
    user_id = int(callback.data.split("_")[-1])
    session: AsyncSession = kwargs["db_session"]
    user_service = UserService(session)
    user = await user_service.get_by_id(user_id)
    if not user:
        await callback.answer("Пользователь не найден.")
        return
    user.collects_hours = not user.collects_hours
    status = "включен" if user.collects_hours else "отключен"
    await callback.message.edit_text(f"Сбор часов для {user.display_name}: {status}")
    await callback.answer(f"Сбор часов {status}!")


# ════════════════════════════════════════════════════════════════════
#  ОЧИСТКА БАЗЫ ДАННЫХ
# ════════════════════════════════════════════════════════════════════

_CLEANUP_TABLES = {
    "tickets": {
        "label": "🎫 Тикеты + сообщения",
        "models": ["ticket_messages", "tickets", "ratings"],
    },
    "timesheets": {
        "label": "🕐 Табели (периоды + записи)",
        "models": ["timesheet_entries", "timesheet_periods"],
    },
    "faq": {
        "label": "📚 FAQ",
        "models": ["faqs"],
    },
    "auto_answers": {
        "label": "🤖 Автоответы",
        "models": ["auto_answers"],
    },
    "quick_replies": {
        "label": "⚡ Быстрые ответы",
        "models": ["quick_replies"],
    },
    "audit": {
        "label": "📝 Аудит лог",
        "models": ["audit_logs"],
    },
    "bot_settings": {
        "label": "⚙ Настройки бота (Google и пр.)",
        "models": ["bot_settings"],
    },
    "all": {
        "label": "💥 Очистить ВСЁ (кроме пользователей и категорий)",
        "models": [
            "ticket_messages", "tickets", "ratings",
            "timesheet_entries", "timesheet_periods",
            "faqs", "auto_answers", "quick_replies",
            "audit_logs", "bot_settings",
        ],
    },
}

# Mapping model name → actual table name in DB
_MODEL_TO_TABLE = {
    "ticket_messages": "ticket_messages",
    "tickets": "tickets",
    "ratings": "ratings",
    "timesheet_entries": "timesheet_entries",
    "timesheet_periods": "timesheet_periods",
    "faqs": "faqs",
    "auto_answers": "auto_answers",
    "quick_replies": "quick_replies",
    "audit_logs": "audit_logs",
    "bot_settings": "bot_settings",
}


@router.callback_query(F.data == "db_cleanup")
async def db_cleanup_menu(callback: CallbackQuery, **kwargs) -> None:
    if not await _check_admin_and_reply(callback, **kwargs):
        return
    session: AsyncSession = kwargs["db_session"]

    # Count rows in each table for display
    from sqlalchemy import text as sa_text
    counts = {}
    for model_name, table_name in _MODEL_TO_TABLE.items():
        try:
            result = await session.execute(sa_text(f"SELECT COUNT(*) FROM {table_name}"))
            counts[model_name] = result.scalar_one()
        except Exception:
            counts[model_name] = "?"

    await callback.message.edit_text(
        "🧹 <b>Очистка данных</b>\n\n"
        "Выберите, что очистить. Пользователи и категории не удаляются.\n\n"
        f"• Тикеты + сообщения: {counts.get('tickets', '?')} / {counts.get('ticket_messages', '?')}\n"
        f"• Оценки: {counts.get('ratings', '?')}\n"
        f"• Табели: {counts.get('timesheet_periods', '?')} / {counts.get('timesheet_entries', '?')}\n"
        f"• FAQ: {counts.get('faqs', '?')}\n"
        f"• Автоответы: {counts.get('auto_answers', '?')}\n"
        f"• Быстрые ответы: {counts.get('quick_replies', '?')}\n"
        f"• Аудит: {counts.get('audit_logs', '?')}\n"
        f"• Настройки бота: {counts.get('bot_settings', '?')}",
        parse_mode="HTML",
        reply_markup=get_db_cleanup_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("db_clean_"))
async def db_cleanup_confirm(callback: CallbackQuery, **kwargs) -> None:
    if not await _check_admin_and_reply(callback, **kwargs):
        return
    section = callback.data.removeprefix("db_clean_")
    if section not in _CLEANUP_TABLES:
        await callback.answer("Неизвестное действие.")
        return

    info = _CLEANUP_TABLES[section]
    await callback.message.edit_text(
        f"⚠ <b>Подтвердите удаление</b>\n\n"
        f"Будут удалены: {info['label']}\n\n"
        f"Это действие <b>невозможно</b> отменить!",
        parse_mode="HTML",
        reply_markup=get_db_cleanup_confirm_keyboard(section),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("db_confirm_clean_"))
async def db_cleanup_execute(callback: CallbackQuery, **kwargs) -> None:
    if not await _check_admin_and_reply(callback, **kwargs):
        return
    section = callback.data.removeprefix("db_confirm_clean_")
    if section not in _CLEANUP_TABLES:
        await callback.answer("Неизвестное действие.")
        return

    info = _CLEANUP_TABLES[section]
    session: AsyncSession = kwargs["db_session"]

    from sqlalchemy import text as sa_text
    deleted_tables = []
    for model_name in info["models"]:
        table_name = _MODEL_TO_TABLE.get(model_name, model_name)
        try:
            # Delete in correct order — child tables first
            result = await session.execute(sa_text(f"DELETE FROM {table_name}"))
            deleted_tables.append(f"• {table_name}: {result.rowcount} строк")
        except Exception as e:
            deleted_tables.append(f"• {table_name}: ошибка — {e}")

    await session.commit()

    # Log the cleanup
    audit_service = AuditService(session)
    await audit_service.log(
        user_id=callback.from_user.id,
        role="admin",
        action=f"db_cleanup_{section}",
        object_type="system",
    )
    await session.commit()

    result_text = "\n".join(deleted_tables)
    await callback.message.edit_text(
        f"✅ <b>Очистка выполнена</b>\n\n{result_text}",
        parse_mode="HTML",
        reply_markup=get_db_cleanup_keyboard(),
    )
    await callback.answer()
