from __future__ import annotations

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.fsm.context import FSMContext

from database.models.role import RoleEnum
from database.session import async_session_factory
from services.user_service import UserService
from services.faq_service import FAQService
from services.auto_answer_service import AutoAnswerService
from services.statistics_service import StatisticsService
from services.export_service import ExportService
from services.audit_service import AuditService
from bot.states.faq_states import FAQManagement
from bot.states.auto_answer_states import AutoAnswerManagement
from bot.states.settings_states import SettingsStates
from bot.keyboards.common import get_main_menu_admin, get_cancel_keyboard
from bot.keyboards.admin import (
    get_users_keyboard,
    get_faq_management_keyboard,
    get_auto_answer_management_keyboard,
    get_admin_faq_list_keyboard,
    get_faq_detail_keyboard,
    get_auto_answer_list_keyboard,
    get_auto_answer_detail_keyboard,
    get_role_change_keyboard,
)
from utils.permissions import is_admin
import tempfile
import os


router = Router()


# ── Проверка прав администратора ───────────────────────────────────

async def _check_admin(message_or_callback) -> bool:
    from_user = getattr(message_or_callback, "from_user", None)
    if not from_user:
        return False

    async with async_session_factory() as session:
        user_service = UserService(session)
        user = await user_service.get_by_telegram_id(from_user.id)
        await session.commit()

    if not user or not user.role:
        return False

    role = user.role.name
    if hasattr(role, "value"):
        role = RoleEnum(role.value)

    return is_admin(role)


async def _check_admin_with_log(callback: CallbackQuery) -> bool:
    result = await _check_admin(callback)
    if not result:
        await callback.answer("Недостаточно прав для выполнения действия.", show_alert=True)
        async with async_session_factory() as session:
            audit_service = AuditService(session)
            await audit_service.log_unauthorized_access(
                user_id=callback.from_user.id,
                role=None,
                action=callback.data or "admin_action",
            )
            await session.commit()
    return result


# ── Пользователи ───────────────────────────────────────────────────

@router.message(F.text == "👥 Пользователи")
async def show_users(message: Message) -> None:
    if not await _check_admin(message):
        await message.answer("Недостаточно прав для выполнения действия.")
        return

    async with async_session_factory() as session:
        user_service = UserService(session)
        users = await user_service.get_all_users()
        await session.commit()

    if not users:
        await message.answer("Пользователи не найдены.")
        return

    await message.answer(
        "👥 Список пользователей:",
        reply_markup=get_users_keyboard(users),
    )


@router.callback_query(F.data.startswith("users_page_"))
async def users_page(callback: CallbackQuery) -> None:
    if not await _check_admin_with_log(callback):
        return

    page = int(callback.data.split("_")[-1])

    async with async_session_factory() as session:
        user_service = UserService(session)
        users = await user_service.get_all_users()
        await session.commit()

    await callback.message.edit_text(
        "👥 Список пользователей:",
        reply_markup=get_users_keyboard(users, page=page),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_user_"))
async def admin_view_user(callback: CallbackQuery) -> None:
    if not await _check_admin_with_log(callback):
        return

    user_id = int(callback.data.split("_")[-1])

    async with async_session_factory() as session:
        user_service = UserService(session)
        user = await user_service.get_by_id(user_id)
        await session.commit()

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
async def set_role(callback: CallbackQuery) -> None:
    if not await _check_admin_with_log(callback):
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

    async with async_session_factory() as session:
        user_service = UserService(session)
        user = await user_service.change_role(
            admin_telegram_id=callback.from_user.id,
            target_user_id=user_id,
            new_role=new_role,
        )
        await session.commit()

    if not user:
        await callback.answer("Пользователь не найден.", show_alert=True)
        return

    role_display = {"admin": "👑 Админ", "operator": "🛠 Оператор", "user": "👤 Пользователь"}.get(role_str, role_str)

    await callback.message.edit_text(
        f"Роль пользователя {user.display_name} изменена на {role_display}."
    )
    await callback.answer("Роль обновлена!")


@router.callback_query(F.data == "back_to_users")
async def back_to_users(callback: CallbackQuery) -> None:
    if not await _check_admin_with_log(callback):
        return

    async with async_session_factory() as session:
        user_service = UserService(session)
        users = await user_service.get_all_users()
        await session.commit()

    await callback.message.edit_text(
        "👥 Список пользователей:",
        reply_markup=get_users_keyboard(users),
    )
    await callback.answer()


# ── FAQ Management ─────────────────────────────────────────────────

@router.message(F.text == "📚 FAQ")
async def admin_faq_menu(message: Message) -> None:
    if not await _check_admin(message):
        await message.answer("Недостаточно прав для выполнения действия.")
        return

    await message.answer(
        "📚 Управление FAQ:",
        reply_markup=get_faq_management_keyboard(),
    )


@router.callback_query(F.data == "admin_faq_menu")
async def admin_faq_menu_callback(callback: CallbackQuery) -> None:
    if not await _check_admin_with_log(callback):
        return

    await callback.message.edit_text(
        "📚 Управление FAQ:",
        reply_markup=get_faq_management_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin_faq_list")
async def admin_faq_list(callback: CallbackQuery) -> None:
    if not await _check_admin_with_log(callback):
        return

    async with async_session_factory() as session:
        faq_service = FAQService(session)
        faqs = await faq_service.get_all()
        await session.commit()

    if not faqs:
        await callback.message.edit_text("FAQ пуст.", reply_markup=None)
        await callback.answer()
        return

    await callback.message.edit_text(
        "📋 Список FAQ:",
        reply_markup=get_admin_faq_list_keyboard(faqs),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_faq_") and ~F.data.startswith("admin_faq_menu") and ~F.data.startswith("admin_faq_list") and ~F.data.startswith("admin_faq_add") and ~F.data.startswith("admin_faq_edit") and ~F.data.startswith("admin_faq_toggle") and ~F.data.startswith("admin_faq_del"))
async def admin_faq_detail(callback: CallbackQuery) -> None:
    if not await _check_admin_with_log(callback):
        return

    faq_id = int(callback.data.split("_")[-1])

    async with async_session_factory() as session:
        faq_service = FAQService(session)
        faq = await faq_service.get_by_id(faq_id)
        await session.commit()

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
async def admin_faq_add(callback: CallbackQuery, state: FSMContext) -> None:
    if not await _check_admin_with_log(callback):
        return

    await state.set_state(FAQManagement.waiting_question)
    await callback.message.answer(
        "Введите вопрос для FAQ:",
        reply_markup=get_cancel_keyboard(),
    )
    await callback.answer()


@router.message(FAQManagement.waiting_question, F.text == "❌ Отмена")
async def cancel_faq_add(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Добавление FAQ отменено.", reply_markup=get_main_menu_admin())


@router.message(FAQManagement.waiting_question)
async def faq_enter_question(message: Message, state: FSMContext) -> None:
    if not message.text or len(message.text.strip()) < 3:
        await message.answer("Вопрос слишком короткий. Попробуйте ещё раз.")
        return

    await state.update_data(question=message.text.strip())
    await state.set_state(FAQManagement.waiting_answer)
    await message.answer("Введите ответ для FAQ:")


@router.message(FAQManagement.waiting_answer)
async def faq_enter_answer(message: Message, state: FSMContext) -> None:
    if not message.text or len(message.text.strip()) < 3:
        await message.answer("Ответ слишком короткий. Попробуйте ещё раз.")
        return

    data = await state.get_data()
    question = data.get("question")

    async with async_session_factory() as session:
        faq_service = FAQService(session)
        await faq_service.create(
            admin_id=message.from_user.id,
            question=question,
            answer=message.text.strip(),
        )
        await session.commit()

    await state.clear()
    await message.answer(
        "FAQ добавлен!",
        reply_markup=get_main_menu_admin(),
    )


@router.callback_query(F.data.startswith("admin_faq_toggle_"))
async def admin_faq_toggle(callback: CallbackQuery) -> None:
    if not await _check_admin_with_log(callback):
        return

    faq_id = int(callback.data.split("_")[-1])

    async with async_session_factory() as session:
        faq_service = FAQService(session)
        faq = await faq_service.toggle_active(callback.from_user.id, faq_id)
        await session.commit()

    if not faq:
        await callback.answer("FAQ не найден.")
        return

    status = "включен" if faq.is_active else "отключен"
    await callback.answer(f"FAQ {status}!")


@router.callback_query(F.data.startswith("admin_faq_del_"))
async def admin_faq_delete(callback: CallbackQuery) -> None:
    if not await _check_admin_with_log(callback):
        return

    faq_id = int(callback.data.split("_")[-1])

    async with async_session_factory() as session:
        faq_service = FAQService(session)
        deleted = await faq_service.delete(callback.from_user.id, faq_id)
        await session.commit()

    if deleted:
        await callback.message.edit_text("FAQ удалён.")
    else:
        await callback.answer("FAQ не найден.")
    await callback.answer()


@router.callback_query(F.data.startswith("admin_faq_edit_"))
async def admin_faq_edit(callback: CallbackQuery, state: FSMContext) -> None:
    if not await _check_admin_with_log(callback):
        return

    faq_id = int(callback.data.split("_")[-1])

    async with async_session_factory() as session:
        faq_service = FAQService(session)
        faq = await faq_service.get_by_id(faq_id)
        await session.commit()

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
async def cancel_faq_edit(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Редактирование FAQ отменено.", reply_markup=get_main_menu_admin())


@router.message(FAQManagement.waiting_edit_question)
async def faq_edit_question(message: Message, state: FSMContext) -> None:
    question = None if (message.text and message.text.strip() == "-") else message.text.strip()
    await state.update_data(new_question=question)
    await state.set_state(FAQManagement.waiting_edit_answer)

    async with async_session_factory() as session:
        data = await state.get_data()
        faq_service = FAQService(session)
        faq = await faq_service.get_by_id(data["faq_id"])
        await session.commit()

    await message.answer(
        f"Текущий ответ:\n{faq.answer}\n\nВведите новый ответ (или отправьте '-' чтобы оставить текущий):",
    )


@router.message(FAQManagement.waiting_edit_answer)
async def faq_edit_answer(message: Message, state: FSMContext) -> None:
    answer = None if (message.text and message.text.strip() == "-") else message.text.strip()
    data = await state.get_data()
    faq_id = data.get("faq_id")
    new_question = data.get("new_question")

    async with async_session_factory() as session:
        faq_service = FAQService(session)
        await faq_service.update(
            admin_id=message.from_user.id,
            faq_id=faq_id,
            question=new_question,
            answer=answer,
        )
        await session.commit()

    await state.clear()
    await message.answer("FAQ обновлён!", reply_markup=get_main_menu_admin())


# ── Автоответы Management ──────────────────────────────────────────

@router.message(F.text == "🤖 Автоответы")
async def admin_auto_answer_menu(message: Message) -> None:
    if not await _check_admin(message):
        await message.answer("Недостаточно прав для выполнения действия.")
        return

    await message.answer(
        "🤖 Управление автоответами:",
        reply_markup=get_auto_answer_management_keyboard(),
    )


@router.callback_query(F.data == "admin_aa_menu")
async def admin_aa_menu_callback(callback: CallbackQuery) -> None:
    if not await _check_admin_with_log(callback):
        return

    await callback.message.edit_text(
        "🤖 Управление автоответами:",
        reply_markup=get_auto_answer_management_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin_aa_list")
async def admin_aa_list(callback: CallbackQuery) -> None:
    if not await _check_admin_with_log(callback):
        return

    async with async_session_factory() as session:
        aa_service = AutoAnswerService(session)
        auto_answers = await aa_service.get_all()
        await session.commit()

    if not auto_answers:
        await callback.message.edit_text("Список автоответов пуст.", reply_markup=None)
        await callback.answer()
        return

    await callback.message.edit_text(
        "📋 Список автоответов:",
        reply_markup=get_auto_answer_list_keyboard(auto_answers),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_aa_") and ~F.data.startswith("admin_aa_menu") and ~F.data.startswith("admin_aa_list") and ~F.data.startswith("admin_aa_add") and ~F.data.startswith("admin_aa_edit") and ~F.data.startswith("admin_aa_toggle") and ~F.data.startswith("admin_aa_del"))
async def admin_aa_detail(callback: CallbackQuery) -> None:
    if not await _check_admin_with_log(callback):
        return

    aa_id = int(callback.data.split("_")[-1])

    async with async_session_factory() as session:
        aa_service = AutoAnswerService(session)
        aa = await aa_service.get_by_id(aa_id)
        await session.commit()

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
async def admin_aa_add(callback: CallbackQuery, state: FSMContext) -> None:
    if not await _check_admin_with_log(callback):
        return

    await state.set_state(AutoAnswerManagement.waiting_keywords)
    await callback.message.answer(
        "Введите ключевые слова через запятую\n(например: зарплата,зп,когда зарплата):",
        reply_markup=get_cancel_keyboard(),
    )
    await callback.answer()


@router.message(AutoAnswerManagement.waiting_keywords, F.text == "❌ Отмена")
async def cancel_aa_add(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Добавление автоответа отменено.", reply_markup=get_main_menu_admin())


@router.message(AutoAnswerManagement.waiting_keywords)
async def aa_enter_keywords(message: Message, state: FSMContext) -> None:
    if not message.text or len(message.text.strip()) < 2:
        await message.answer("Ключевые слова слишком короткие. Попробуйте ещё раз.")
        return

    await state.update_data(keywords=message.text.strip())
    await state.set_state(AutoAnswerManagement.waiting_answer)
    await message.answer("Введите текст автоответа:")


@router.message(AutoAnswerManagement.waiting_answer)
async def aa_enter_answer(message: Message, state: FSMContext) -> None:
    if not message.text or len(message.text.strip()) < 3:
        await message.answer("Ответ слишком короткий. Попробуйте ещё раз.")
        return

    data = await state.get_data()
    keywords = data.get("keywords")

    async with async_session_factory() as session:
        aa_service = AutoAnswerService(session)
        await aa_service.create(
            admin_id=message.from_user.id,
            keywords=keywords,
            answer=message.text.strip(),
        )
        await session.commit()

    await state.clear()
    await message.answer(
        "Автоответ добавлен!",
        reply_markup=get_main_menu_admin(),
    )


@router.callback_query(F.data.startswith("admin_aa_toggle_"))
async def admin_aa_toggle(callback: CallbackQuery) -> None:
    if not await _check_admin_with_log(callback):
        return

    aa_id = int(callback.data.split("_")[-1])

    async with async_session_factory() as session:
        aa_service = AutoAnswerService(session)
        aa = await aa_service.toggle_active(callback.from_user.id, aa_id)
        await session.commit()

    if not aa:
        await callback.answer("Автоответ не найден.")
        return

    status = "включен" if aa.is_active else "отключен"
    await callback.answer(f"Автоответ {status}!")


@router.callback_query(F.data.startswith("admin_aa_del_"))
async def admin_aa_delete(callback: CallbackQuery) -> None:
    if not await _check_admin_with_log(callback):
        return

    aa_id = int(callback.data.split("_")[-1])

    async with async_session_factory() as session:
        aa_service = AutoAnswerService(session)
        deleted = await aa_service.delete(callback.from_user.id, aa_id)
        await session.commit()

    if deleted:
        await callback.message.edit_text("Автоответ удалён.")
    else:
        await callback.answer("Автоответ не найден.")
    await callback.answer()


@router.callback_query(F.data.startswith("admin_aa_edit_"))
async def admin_aa_edit(callback: CallbackQuery, state: FSMContext) -> None:
    if not await _check_admin_with_log(callback):
        return

    aa_id = int(callback.data.split("_")[-1])

    async with async_session_factory() as session:
        aa_service = AutoAnswerService(session)
        aa = await aa_service.get_by_id(aa_id)
        await session.commit()

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
async def cancel_aa_edit(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Редактирование автоответа отменено.", reply_markup=get_main_menu_admin())


@router.message(AutoAnswerManagement.waiting_edit_keywords)
async def aa_edit_keywords(message: Message, state: FSMContext) -> None:
    keywords = None if (message.text and message.text.strip() == "-") else message.text.strip()
    await state.update_data(new_keywords=keywords)
    await state.set_state(AutoAnswerManagement.waiting_edit_answer)

    async with async_session_factory() as session:
        data = await state.get_data()
        aa_service = AutoAnswerService(session)
        aa = await aa_service.get_by_id(data["aa_id"])
        await session.commit()

    await message.answer(
        f"Текущий ответ:\n{aa.answer}\n\nВведите новый ответ (или '-' чтобы оставить текущий):",
    )


@router.message(AutoAnswerManagement.waiting_edit_answer)
async def aa_edit_answer(message: Message, state: FSMContext) -> None:
    answer = None if (message.text and message.text.strip() == "-") else message.text.strip()
    data = await state.get_data()
    aa_id = data.get("aa_id")
    new_keywords = data.get("new_keywords")

    async with async_session_factory() as session:
        aa_service = AutoAnswerService(session)
        await aa_service.update(
            admin_id=message.from_user.id,
            auto_answer_id=aa_id,
            keywords=new_keywords,
            answer=answer,
        )
        await session.commit()

    await state.clear()
    await message.answer("Автоответ обновлён!", reply_markup=get_main_menu_admin())


# ── Статистика ─────────────────────────────────────────────────────

@router.message(F.text == "📊 Статистика")
async def show_statistics(message: Message) -> None:
    if not await _check_admin(message):
        await message.answer("Недостаточно прав для выполнения действия.")
        return

    async with async_session_factory() as session:
        stats_service = StatisticsService(session)
        stats = await stats_service.get_statistics()
        await session.commit()

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
async def export_data(message: Message) -> None:
    if not await _check_admin(message):
        await message.answer("Недостаточно прав для выполнения действия.")
        return

    await message.answer("Выполняется выгрузка данных...")

    async with async_session_factory() as session:
        export_service = ExportService(session)
        buffer = await export_service.export_tickets_to_excel(message.from_user.id)
        await session.commit()

    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp.write(buffer.getvalue())
        tmp_path = tmp.name

    try:
        doc = FSInputFile(tmp_path, filename="helpdesk_tickets.xlsx")
        await message.answer_document(doc, caption="📊 Выгрузка обращений")
    finally:
        os.unlink(tmp_path)


# ── Настройки ──────────────────────────────────────────────────────

@router.message(F.text == "⚙ Настройки")
async def show_settings(message: Message) -> None:
    if not await _check_admin(message):
        await message.answer("Недостаточно прав для выполнения действия.")
        return

    async with async_session_factory() as session:
        audit_service = AuditService(session)
        await audit_service.log(
            user_id=message.from_user.id,
            role="admin",
            action="enter_settings",
            object_type="system",
        )
        await session.commit()

    text = (
        "⚙ <b>Настройки</b>\n\n"
        "Для управления настройками используйте разделы выше.\n\n"
        "Доступные действия:\n"
        "• 👥 Управление пользователями и ролями\n"
        "• 📚 Управление FAQ\n"
        "• 🤖 Управление автоответами\n"
        "• 📊 Просмотр статистики\n"
        "• 📤 Выгрузка данных"
    )
    await message.answer(text, parse_mode="HTML")
