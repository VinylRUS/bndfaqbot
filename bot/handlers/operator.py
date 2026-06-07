from __future__ import annotations

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.role import RoleEnum
from database.models.ticket import TicketStatus
from services.user_service import UserService
from services.ticket_service import TicketService
from services.quick_reply_service import QuickReplyService
from services.audit_service import AuditService
from bot.states.ticket_states import OperatorReply
from bot.states.quick_reply_states import QuickReplyManagement
from bot.keyboards.common import get_main_menu_operator, get_cancel_keyboard
from bot.keyboards.operator import (
    get_new_tickets_keyboard,
    get_operator_active_keyboard,
    get_operator_history_keyboard,
    get_ticket_actions_keyboard,
)
from bot.keyboards.quick_reply import (
    get_quick_replies_keyboard,
    get_quick_reply_detail_keyboard,
    get_save_quick_reply_keyboard,
)
from bot.keyboards.user import get_rating_keyboard
from utils.permissions import can_handle_tickets


router = Router()


# ── Проверка роли оператора ────────────────────────────────────────

def _is_operator(**kwargs) -> bool:
    """Check operator/admin role from middleware data."""
    user_role: RoleEnum | None = kwargs.get("user_role")
    return user_role is not None and can_handle_tickets(user_role)


async def _check_operator_and_reply(callback: CallbackQuery, **kwargs) -> bool:
    if _is_operator(**kwargs):
        return True
    await callback.answer("Недостаточно прав для выполнения действия.", show_alert=True)
    session: AsyncSession | None = kwargs.get("db_session")
    if session:
        audit_service = AuditService(session)
        await audit_service.log_unauthorized_access(
            user_id=callback.from_user.id, role=None,
            action=callback.data or "operator_action",
        )
    return False


# ── Новые тикеты ───────────────────────────────────────────────────

@router.message(F.text == "📥 Новые тикеты")
async def show_new_tickets(message: Message, **kwargs) -> None:
    if not _is_operator(**kwargs):
        await message.answer("Недостаточно прав для выполнения действия.")
        return
    session: AsyncSession = kwargs["db_session"]
    ticket_service = TicketService(session)
    tickets = await ticket_service.get_new_tickets()
    if not tickets:
        await message.answer("Нет новых тикетов.")
        return
    await message.answer("📥 Новые тикеты:", reply_markup=get_new_tickets_keyboard(tickets))


# ── В работе ───────────────────────────────────────────────────────

@router.message(F.text == "🛠 В работе")
async def show_active_tickets(message: Message, **kwargs) -> None:
    if not _is_operator(**kwargs):
        await message.answer("Недостаточно прав для выполнения действия.")
        return
    session: AsyncSession = kwargs["db_session"]
    ticket_service = TicketService(session)
    tickets = await ticket_service.get_operator_active(message.from_user.id)
    if not tickets:
        await message.answer("У вас нет тикетов в работе.")
        return
    await message.answer("🛠 Тикеты в работе:", reply_markup=get_operator_active_keyboard(tickets))


# ── История ────────────────────────────────────────────────────────

@router.message(F.text == "📜 История")
async def show_history(message: Message, **kwargs) -> None:
    if not _is_operator(**kwargs):
        await message.answer("Недостаточно прав для выполнения действия.")
        return
    session: AsyncSession = kwargs["db_session"]
    ticket_service = TicketService(session)
    tickets = await ticket_service.get_operator_history(message.from_user.id)
    if not tickets:
        await message.answer("История пуста.")
        return
    await message.answer("📜 История закрытых тикетов:", reply_markup=get_operator_history_keyboard(tickets))


# ── Просмотр тикета оператором ─────────────────────────────────────

@router.callback_query(F.data.startswith("op_ticket_"))
async def operator_view_ticket(callback: CallbackQuery, **kwargs) -> None:
    if not await _check_operator_and_reply(callback, **kwargs):
        return
    ticket_id = int(callback.data.split("_")[-1])
    session: AsyncSession = kwargs["db_session"]
    ticket_service = TicketService(session)
    ticket = await ticket_service.get_by_id(ticket_id)
    messages = await ticket_service.get_ticket_messages(ticket_id)
    if not ticket:
        await callback.answer("Тикет не найден.")
        return
    text = _format_operator_ticket(ticket, messages)
    can_take = ticket.status == TicketStatus.NEW
    can_reply = (
        ticket.status in (TicketStatus.IN_PROGRESS, TicketStatus.ANSWERED)
        and ticket.operator_id == callback.from_user.id
    )
    can_close = can_reply
    keyboard = get_ticket_actions_keyboard(
        ticket_id=ticket.id, can_take=can_take, can_reply=can_reply,
        can_close=can_close, can_quick_reply=can_reply,
    )
    await callback.message.answer(text, parse_mode="HTML", reply_markup=keyboard)
    await callback.answer()


# ── Взять тикет в работу (сразу переход к диалогу) ────────────────

@router.callback_query(F.data.startswith("take_"))
async def take_ticket(callback: CallbackQuery, state: FSMContext, **kwargs) -> None:
    if not await _check_operator_and_reply(callback, **kwargs):
        return
    ticket_id = int(callback.data.split("_")[1])
    session: AsyncSession = kwargs["db_session"]
    ticket_service = TicketService(session)
    ticket = await ticket_service.assign_operator(ticket_id, callback.from_user.id)
    if not ticket:
        await callback.answer("Не удалось взять тикет. Возможно, он уже взят другим оператором.", show_alert=True)
        return
    bot: Bot = kwargs["bot"]
    try:
        await bot.send_message(ticket.author_id, f"Ваше обращение #{ticket.number} взято в работу. Оператор ответит вам в ближайшее время.")
    except Exception:
        pass
    await state.set_state(OperatorReply.writing_reply)
    await state.update_data(ticket_id=ticket.id)
    await callback.message.edit_text(f"Вы взяли тикет #{ticket.number} в работу.", reply_markup=None)
    await callback.message.answer(
        f"✉ Ответ на тикет #{ticket.number}:\n\nВведите текст ответа "
        f"(или нажмите «❌ Отмена» чтобы вернуться к списку):",
        reply_markup=get_cancel_keyboard(),
    )
    await callback.answer()


# ── Ответить на тикет ─────────────────────────────────────────────

@router.callback_query(F.data.startswith("reply_"))
async def reply_to_ticket(callback: CallbackQuery, state: FSMContext, **kwargs) -> None:
    if not await _check_operator_and_reply(callback, **kwargs):
        return
    ticket_id = int(callback.data.split("_")[1])
    session: AsyncSession = kwargs["db_session"]
    ticket_service = TicketService(session)
    ticket = await ticket_service.get_by_id(ticket_id)
    if not ticket or ticket.operator_id != callback.from_user.id:
        await callback.answer("Вы не можете ответить на этот тикет.", show_alert=True)
        return
    await state.set_state(OperatorReply.writing_reply)
    await state.update_data(ticket_id=ticket_id)
    await callback.message.answer(
        f"✉ Ответ на тикет #{ticket.number}:\n\nВведите текст ответа (или фото/документ с подписью):",
        reply_markup=get_cancel_keyboard(),
    )
    await callback.answer()


# ── Быстрый ответ (выбор шаблона) ──────────────────────────────────

@router.callback_query(F.data.startswith("quick_reply_"))
async def quick_reply_select(callback: CallbackQuery, **kwargs) -> None:
    if not await _check_operator_and_reply(callback, **kwargs):
        return
    session: AsyncSession = kwargs["db_session"]
    quick_service = QuickReplyService(session)
    replies = await quick_service.get_user_replies(callback.from_user.id)
    if not replies:
        await callback.answer("У вас нет сохранённых шаблонов. Ответьте текстом и сохраните.", show_alert=True)
        return
    await callback.message.answer("⚡ Выберите быстрый ответ:", reply_markup=get_quick_replies_keyboard(replies))
    await callback.answer()


@router.callback_query(F.data.startswith("quick_") and ~F.data.startswith("quick_reply_") and ~F.data.startswith("quick_add") and ~F.data.startswith("quick_del_") and ~F.data.startswith("save_quick_") and ~F.data.startswith("nosave_quick_"))
async def use_quick_reply(callback: CallbackQuery, state: FSMContext, **kwargs) -> None:
    """Operator selected a quick reply template — send it as the reply."""
    quick_id = int(callback.data.split("_")[1])
    session: AsyncSession = kwargs["db_session"]
    quick_service = QuickReplyService(session)
    reply = await quick_service.get_by_id(quick_id)
    if not reply or reply.user_id != callback.from_user.id:
        await callback.answer("Шаблон не найден.")
        return

    # Get ticket_id from FSM state (should be in OperatorReply)
    state_data = await state.get_data()
    ticket_id = state_data.get("ticket_id")
    if not ticket_id:
        await callback.answer("Сначала выберите тикет для ответа.", show_alert=True)
        return

    ticket_service = TicketService(session)
    result = await ticket_service.add_message(
        ticket_id=ticket_id, sender_id=callback.from_user.id, text=reply.text,
    )
    await state.clear()

    if result:
        ticket = result["ticket"]
        bot: Bot = kwargs["bot"]
        try:
            await bot.send_message(ticket.author_id, f"📩 Ответ на обращение #{ticket.number}:\n\n{reply.text}")
        except Exception:
            pass

    await callback.message.edit_text("✅ Быстрый ответ отправлен.")
    await callback.message.answer("Ответ отправлен пользователю.", reply_markup=get_main_menu_operator())
    await callback.message.answer(
        f"Тикет #{ticket_id}",
        reply_markup=get_ticket_actions_keyboard(ticket_id=ticket_id, can_reply=True, can_close=True, can_quick_reply=True),
    )
    await callback.answer()


# ── Отмена ответа ──────────────────────────────────────────────────

@router.message(OperatorReply.writing_reply, F.text == "❌ Отмена")
async def cancel_reply(message: Message, state: FSMContext, **kwargs) -> None:
    await state.clear()
    session: AsyncSession = kwargs["db_session"]
    ticket_service = TicketService(session)
    tickets = await ticket_service.get_operator_active(message.from_user.id)
    if tickets:
        await message.answer("Ответ отменён. Ваши тикеты в работе:", reply_markup=get_main_menu_operator())
        await message.answer("🛠 Тикеты в работе:", reply_markup=get_operator_active_keyboard(tickets))
    else:
        await message.answer("Ответ отменён.", reply_markup=get_main_menu_operator())


# ── Отправка ответа (текст) ───────────────────────────────────────

@router.message(OperatorReply.writing_reply, F.text)
async def send_reply(message: Message, state: FSMContext, **kwargs) -> None:
    if not message.text or len(message.text.strip()) < 1:
        await message.answer("Текст ответа не может быть пустым.")
        return
    state_data = await state.get_data()
    ticket_id = state_data.get("ticket_id")
    session: AsyncSession = kwargs["db_session"]
    ticket_service = TicketService(session)
    result = await ticket_service.add_message(
        ticket_id=ticket_id, sender_id=message.from_user.id, text=message.text.strip(),
    )
    await state.clear()
    if result:
        ticket = result["ticket"]
        bot: Bot = kwargs["bot"]
        try:
            await bot.send_message(ticket.author_id, f"📩 Ответ на обращение #{ticket.number}:\n\n{message.text.strip()}")
        except Exception:
            pass
    await message.answer("✅ Ответ отправлен пользователю.", reply_markup=get_main_menu_operator())
    # Prompt to save as quick reply
    await message.answer(
        "Сохранить как быстрый ответ?",
        reply_markup=get_save_quick_reply_keyboard(ticket_id),
    )
    # Show ticket actions
    await message.answer(
        f"Тикет #{ticket_id}",
        reply_markup=get_ticket_actions_keyboard(ticket_id=ticket_id, can_reply=True, can_close=True, can_quick_reply=True),
    )


# ── Отправка ответа (фото/документ) ───────────────────────────────

@router.message(OperatorReply.writing_reply, F.photo | F.document)
async def send_reply_attachment(message: Message, state: FSMContext, **kwargs) -> None:
    state_data = await state.get_data()
    ticket_id = state_data.get("ticket_id")
    session: AsyncSession = kwargs["db_session"]
    ticket_service = TicketService(session)

    # Get file info
    if message.photo:
        file_id = message.photo[-1].file_id
        file_type = "photo"
        caption = message.caption or ""
    elif message.document:
        file_id = message.document.file_id
        file_type = "document"
        caption = message.caption or ""
    else:
        await message.answer("Неподдерживаемый тип файла.")
        return

    result = await ticket_service.add_message(
        ticket_id=ticket_id, sender_id=message.from_user.id, text=caption,
        file_id=file_id, file_type=file_type,
    )
    await state.clear()

    if result:
        ticket = result["ticket"]
        bot: Bot = kwargs["bot"]
        try:
            if file_type == "photo":
                await bot.send_photo(ticket.author_id, photo=file_id, caption=f"📩 Ответ на обращение #{ticket.number}:\n\n{caption}")
            else:
                await bot.send_document(ticket.author_id, document=file_id, caption=f"📩 Ответ на обращение #{ticket.number}:\n\n{caption}")
        except Exception:
            pass

    await message.answer("✅ Ответ с вложением отправлен пользователю.", reply_markup=get_main_menu_operator())
    await message.answer(
        f"Тикет #{ticket_id}",
        reply_markup=get_ticket_actions_keyboard(ticket_id=ticket_id, can_reply=True, can_close=True, can_quick_reply=True),
    )


# ── Сохранить / не сохранять быстрый ответ ─────────────────────────

@router.callback_query(F.data.startswith("save_quick_"))
async def save_quick_reply(callback: CallbackQuery, state: FSMContext, **kwargs) -> None:
    await state.set_state(QuickReplyManagement.waiting_name)
    await state.update_data(quick_text_source="last_reply")  # marker
    await callback.message.edit_text("Введите название для быстрого ответа (или отправьте «-» чтобы использовать начало текста):")
    await callback.answer()


@router.callback_query(F.data.startswith("nosave_quick_"))
async def nosave_quick_reply(callback: CallbackQuery, state: FSMContext, **kwargs) -> None:
    await callback.message.edit_text("Ок, ответ не сохранён.")
    await callback.answer()


@router.message(QuickReplyManagement.waiting_name)
async def quick_reply_enter_name(message: Message, state: FSMContext, **kwargs) -> None:
    name = message.text.strip() if message.text else ""
    if name == "-":
        name = ""  # will auto-generate from text
    await state.update_data(quick_name=name)
    await state.set_state(QuickReplyManagement.waiting_text)
    await message.answer("Введите текст быстрого ответа:")


@router.message(QuickReplyManagement.waiting_text)
async def quick_reply_enter_text(message: Message, state: FSMContext, **kwargs) -> None:
    text = message.text.strip() if message.text else ""
    if len(text) < 2:
        await message.answer("Текст слишком короткий.")
        return
    state_data = await state.get_data()
    name = state_data.get("quick_name", "")
    session: AsyncSession = kwargs["db_session"]
    quick_service = QuickReplyService(session)
    await quick_service.create(user_id=message.from_user.id, name=name, text=text)
    await state.clear()
    await message.answer("✅ Быстрый ответ сохранён!", reply_markup=get_main_menu_operator())


# ── Управление быстрыми ответами (из меню) ─────────────────────────

@router.message(F.text == "⚡ Быстрые ответы")
async def show_quick_replies_menu(message: Message, **kwargs) -> None:
    session: AsyncSession = kwargs["db_session"]
    quick_service = QuickReplyService(session)
    replies = await quick_service.get_user_replies(message.from_user.id)
    if not replies:
        await message.answer("У вас нет сохранённых шаблонов. Они появятся после отправки ответов.")
        return
    await message.answer("⚡ Ваши быстрые ответы:", reply_markup=get_quick_replies_keyboard(replies))


@router.callback_query(F.data == "quick_list")
async def quick_list_callback(callback: CallbackQuery, **kwargs) -> None:
    session: AsyncSession = kwargs["db_session"]
    quick_service = QuickReplyService(session)
    replies = await quick_service.get_user_replies(callback.from_user.id)
    await callback.message.edit_text("⚡ Ваши быстрые ответы:", reply_markup=get_quick_replies_keyboard(replies))
    await callback.answer()


@router.callback_query(F.data == "quick_add")
async def quick_add_callback(callback: CallbackQuery, state: FSMContext, **kwargs) -> None:
    await state.set_state(QuickReplyManagement.waiting_name)
    await callback.message.answer("Введите название для быстрого ответа (или «-» для автогенерации):", reply_markup=get_cancel_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("quick_del_"))
async def quick_delete(callback: CallbackQuery, **kwargs) -> None:
    quick_id = int(callback.data.split("_")[-1])
    session: AsyncSession = kwargs["db_session"]
    quick_service = QuickReplyService(session)
    await quick_service.delete(quick_id)
    await callback.message.edit_text("Шаблон удалён.")
    await callback.answer()


# ── Закрыть тикет ─────────────────────────────────────────────────

@router.callback_query(F.data.startswith("close_"))
async def close_ticket(callback: CallbackQuery, **kwargs) -> None:
    if not await _check_operator_and_reply(callback, **kwargs):
        return
    ticket_id = int(callback.data.split("_")[1])
    session: AsyncSession = kwargs["db_session"]
    ticket_service = TicketService(session)
    ticket = await ticket_service.get_by_id(ticket_id)
    if not ticket or ticket.operator_id != callback.from_user.id:
        await callback.answer("Вы не можете закрыть этот тикет.", show_alert=True)
        return
    closed_ticket = await ticket_service.close_ticket(ticket_id, callback.from_user.id)
    if not closed_ticket:
        await callback.answer("Не удалось закрыть тикет.", show_alert=True)
        return
    await callback.message.edit_text(f"Тикет #{closed_ticket.number} закрыт.", reply_markup=None)
    bot: Bot = kwargs["bot"]
    try:
        await bot.send_message(
            closed_ticket.author_id,
            f"Ваше обращение #{closed_ticket.number} закрыто.\n\nОцените качество ответа:",
            reply_markup=get_rating_keyboard(closed_ticket.id),
        )
    except Exception:
        pass
    await callback.answer()


# ── Назад в меню оператора ────────────────────────────────────────

@router.callback_query(F.data == "back_to_op_menu")
async def back_to_op_menu(callback: CallbackQuery, state: FSMContext, **kwargs) -> None:
    await state.clear()
    await callback.message.answer("Главное меню 🛠", reply_markup=get_main_menu_operator())
    await callback.answer()


# ── Вспомогательные ───────────────────────────────────────────────

def _format_operator_ticket(ticket, messages) -> str:
    status_emoji = {"NEW": "🆕", "IN_PROGRESS": "🛠", "ANSWERED": "✅", "CLOSED": "🔒"}
    status_str = ticket.status.value if hasattr(ticket.status, "value") else str(ticket.status)
    emoji = status_emoji.get(status_str, "❓")
    text = (
        f"<b>Тикет #{ticket.number}</b>\n"
        f"Статус: {emoji} {status_str}\n"
        f"Категория: {ticket.category.full_name if ticket.category else '—'}\n"
        f"Пользователь: {ticket.author.display_name if ticket.author else '—'}\n"
        f"Телефон: {ticket.author.phone or '—'}\n"
        f"Дата создания: {ticket.created_at.strftime('%d.%m.%Y %H:%M') if ticket.created_at else '—'}\n"
    )
    if ticket.operator:
        text += f"Оператор: {ticket.operator.display_name}\n"
    text += f"\n<b>Обращение:</b>\n{ticket.text}"
    if messages:
        text += "\n\n💬 <b>Переписка:</b>"
        for msg in messages:
            sender = "Пользователь" if msg.sender_id == ticket.author_id else "Оператор"
            content = msg.text or ""
            if msg.file_type == "photo":
                content = "📷 Фото" + (f": {content}" if content else "")
            elif msg.file_type == "document":
                content = "📎 Файл" + (f": {content}" if content else "")
            text += f"\n<b>{sender}:</b> {content}"
    return text
