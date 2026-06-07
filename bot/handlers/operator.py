from __future__ import annotations

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from database.models.role import RoleEnum
from database.models.ticket import TicketStatus
from services.user_service import UserService
from services.ticket_service import TicketService
from services.audit_service import AuditService
from bot.states.ticket_states import OperatorReply
from bot.keyboards.common import get_main_menu_operator, get_cancel_keyboard
from bot.keyboards.operator import (
    get_new_tickets_keyboard,
    get_operator_active_keyboard,
    get_operator_history_keyboard,
    get_ticket_actions_keyboard,
)
from bot.keyboards.user import get_rating_keyboard
from utils.permissions import can_handle_tickets


router = Router()


# ── Проверка роли оператора ────────────────────────────────────────

async def _check_operator(data: dict) -> bool:
    """Check operator/admin role from middleware data (no extra DB query)."""
    user_role: RoleEnum | None = data.get("user_role")
    return user_role is not None and can_handle_tickets(user_role)


async def _check_operator_and_reply(callback: CallbackQuery, data: dict) -> bool:
    """Check operator + send error + log unauthorized access."""
    if await _check_operator(data):
        return True

    await callback.answer("Недостаточно прав для выполнения действия.", show_alert=True)
    session = data.get("db_session")
    if session:
        audit_service = AuditService(session)
        await audit_service.log_unauthorized_access(
            user_id=callback.from_user.id,
            role=None,
            action=callback.data or "operator_action",
        )
    return False


# ── Новые тикеты ───────────────────────────────────────────────────

@router.message(F.text == "📥 Новые тикеты")
async def show_new_tickets(message: Message, data: dict) -> None:
    if not await _check_operator(data):
        await message.answer("Недостаточно прав для выполнения действия.")
        return

    session = data["db_session"]
    ticket_service = TicketService(session)
    tickets = await ticket_service.get_new_tickets()

    if not tickets:
        await message.answer("Нет новых тикетов.")
        return

    await message.answer(
        "📥 Новые тикеты:",
        reply_markup=get_new_tickets_keyboard(tickets),
    )


# ── В работе ───────────────────────────────────────────────────────

@router.message(F.text == "🛠 В работе")
async def show_active_tickets(message: Message, data: dict) -> None:
    if not await _check_operator(data):
        await message.answer("Недостаточно прав для выполнения действия.")
        return

    session = data["db_session"]
    ticket_service = TicketService(session)
    tickets = await ticket_service.get_operator_active(message.from_user.id)

    if not tickets:
        await message.answer("У вас нет тикетов в работе.")
        return

    await message.answer(
        "🛠 Тикеты в работе:",
        reply_markup=get_operator_active_keyboard(tickets),
    )


# ── История ────────────────────────────────────────────────────────

@router.message(F.text == "📜 История")
async def show_history(message: Message, data: dict) -> None:
    if not await _check_operator(data):
        await message.answer("Недостаточно прав для выполнения действия.")
        return

    session = data["db_session"]
    ticket_service = TicketService(session)
    tickets = await ticket_service.get_operator_history(message.from_user.id)

    if not tickets:
        await message.answer("История пуста.")
        return

    await message.answer(
        "📜 История закрытых тикетов:",
        reply_markup=get_operator_history_keyboard(tickets),
    )


# ── Просмотр тикета оператором ─────────────────────────────────────

@router.callback_query(F.data.startswith("op_ticket_"))
async def operator_view_ticket(callback: CallbackQuery, data: dict) -> None:
    if not await _check_operator_and_reply(callback, data):
        return

    ticket_id = int(callback.data.split("_")[-1])

    session = data["db_session"]
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
    can_close = (
        ticket.status in (TicketStatus.IN_PROGRESS, TicketStatus.ANSWERED)
        and ticket.operator_id == callback.from_user.id
    )

    keyboard = get_ticket_actions_keyboard(
        ticket_id=ticket.id,
        can_take=can_take,
        can_reply=can_reply,
        can_close=can_close,
    )

    await callback.message.answer(text, parse_mode="HTML", reply_markup=keyboard)
    await callback.answer()


# ── Взять тикет в работу ──────────────────────────────────────────

@router.callback_query(F.data.startswith("take_"))
async def take_ticket(callback: CallbackQuery, data: dict) -> None:
    if not await _check_operator_and_reply(callback, data):
        return

    ticket_id = int(callback.data.split("_")[1])

    session = data["db_session"]
    ticket_service = TicketService(session)
    ticket = await ticket_service.assign_operator(ticket_id, callback.from_user.id)

    if not ticket:
        await callback.answer("Не удалось взять тикет. Возможно, он уже взят другим оператором.", show_alert=True)
        return

    await callback.message.edit_text(
        f"Вы взяли тикет #{ticket.number} в работу.",
        reply_markup=None,
    )

    # Notify the user using the shared bot instance
    bot: Bot = data["bot"]
    try:
        await bot.send_message(
            ticket.author_id,
            f"Ваше обращение #{ticket.number} взято в работу. Оператор ответит вам в ближайшее время.",
        )
    except Exception:
        pass  # User may have blocked the bot

    await callback.answer()


# ── Ответить на тикет ─────────────────────────────────────────────

@router.callback_query(F.data.startswith("reply_"))
async def reply_to_ticket(callback: CallbackQuery, state: FSMContext, data: dict) -> None:
    if not await _check_operator_and_reply(callback, data):
        return

    ticket_id = int(callback.data.split("_")[1])

    session = data["db_session"]
    ticket_service = TicketService(session)
    ticket = await ticket_service.get_by_id(ticket_id)

    if not ticket or ticket.operator_id != callback.from_user.id:
        await callback.answer("Вы не можете ответить на этот тикет.", show_alert=True)
        return

    await state.set_state(OperatorReply.writing_reply)
    await state.update_data(ticket_id=ticket_id)

    await callback.message.answer(
        f"Ответ на тикет #{ticket.number}:\n\nВведите текст ответа:",
        reply_markup=get_cancel_keyboard(),
    )
    await callback.answer()


@router.message(OperatorReply.writing_reply, F.text == "❌ Отмена")
async def cancel_reply(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Ответ отменён.", reply_markup=get_main_menu_operator())


@router.message(OperatorReply.writing_reply)
async def send_reply(message: Message, state: FSMContext, data: dict) -> None:
    if not message.text or len(message.text.strip()) < 1:
        await message.answer("Текст ответа не может быть пустым.")
        return

    state_data = await state.get_data()
    ticket_id = state_data.get("ticket_id")

    session = data["db_session"]
    ticket_service = TicketService(session)
    result = await ticket_service.add_message(
        ticket_id=ticket_id,
        sender_id=message.from_user.id,
        text=message.text.strip(),
    )

    await state.clear()

    if result:
        ticket = result["ticket"]
        # Notify the user using the shared bot instance
        bot: Bot = data["bot"]
        try:
            await bot.send_message(
                ticket.author_id,
                f"📩 Ответ на обращение #{ticket.number}:\n\n{message.text.strip()}",
            )
        except Exception:
            pass  # User may have blocked the bot

    await message.answer(
        "Ответ отправлен пользователю.",
        reply_markup=get_main_menu_operator(),
    )


# ── Закрыть тикет ─────────────────────────────────────────────────

@router.callback_query(F.data.startswith("close_"))
async def close_ticket(callback: CallbackQuery, data: dict) -> None:
    if not await _check_operator_and_reply(callback, data):
        return

    ticket_id = int(callback.data.split("_")[1])

    session = data["db_session"]
    ticket_service = TicketService(session)
    ticket = await ticket_service.get_by_id(ticket_id)

    if not ticket or ticket.operator_id != callback.from_user.id:
        await callback.answer("Вы не можете закрыть этот тикет.", show_alert=True)
        return

    closed_ticket = await ticket_service.close_ticket(ticket_id, callback.from_user.id)

    if not closed_ticket:
        await callback.answer("Не удалось закрыть тикет.", show_alert=True)
        return

    await callback.message.edit_text(
        f"Тикет #{closed_ticket.number} закрыт.",
        reply_markup=None,
    )

    # Notify user and request rating using the shared bot instance
    bot: Bot = data["bot"]
    try:
        await bot.send_message(
            closed_ticket.author_id,
            f"Ваше обращение #{closed_ticket.number} закрыто.\n\nОцените качество ответа:",
            reply_markup=get_rating_keyboard(closed_ticket.id),
        )
    except Exception:
        pass  # User may have blocked the bot

    await callback.answer()


# ── Назад в меню оператора ────────────────────────────────────────

@router.callback_query(F.data == "back_to_op_menu")
async def back_to_op_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.answer("Главное меню 🛠", reply_markup=get_main_menu_operator())
    await callback.answer()


# ── Вспомогательные ───────────────────────────────────────────────

def _format_operator_ticket(ticket, messages) -> str:
    status_emoji = {
        "NEW": "🆕",
        "IN_PROGRESS": "🛠",
        "ANSWERED": "✅",
        "CLOSED": "🔒",
    }
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
            text += f"\n<b>{sender}:</b> {msg.text}"

    return text
