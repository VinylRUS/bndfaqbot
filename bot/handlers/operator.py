from __future__ import annotations

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from database.models.role import RoleEnum
from database.models.ticket import TicketStatus
from database.session import async_session_factory
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
from utils.permissions import can_handle_tickets


router = Router()


# ── Проверка роли оператора ────────────────────────────────────────

async def _check_operator(message_or_callback) -> bool:
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

    return can_handle_tickets(role)


async def _check_operator_with_log(callback: CallbackQuery) -> bool:
    result = await _check_operator(callback)
    if not result:
        await callback.answer("Недостаточно прав для выполнения действия.", show_alert=True)
        async with async_session_factory() as session:
            audit_service = AuditService(session)
            await audit_service.log_unauthorized_access(
                user_id=callback.from_user.id,
                role=None,
                action=callback.data or "operator_action",
            )
            await session.commit()
    return result


# ── Новые тикеты ───────────────────────────────────────────────────

@router.message(F.text == "📥 Новые тикеты")
async def show_new_tickets(message: Message) -> None:
    if not await _check_operator(message):
        await message.answer("Недостаточно прав для выполнения действия.")
        return

    async with async_session_factory() as session:
        ticket_service = TicketService(session)
        tickets = await ticket_service.get_new_tickets()
        await session.commit()

    if not tickets:
        await message.answer("Нет новых тикетов.")
        return

    await message.answer(
        "📥 Новые тикеты:",
        reply_markup=get_new_tickets_keyboard(tickets),
    )


# ── В работе ───────────────────────────────────────────────────────

@router.message(F.text == "🛠 В работе")
async def show_active_tickets(message: Message) -> None:
    if not await _check_operator(message):
        await message.answer("Недостаточно прав для выполнения действия.")
        return

    async with async_session_factory() as session:
        ticket_service = TicketService(session)
        tickets = await ticket_service.get_operator_active(message.from_user.id)
        await session.commit()

    if not tickets:
        await message.answer("У вас нет тикетов в работе.")
        return

    await message.answer(
        "🛠 Тикеты в работе:",
        reply_markup=get_operator_active_keyboard(tickets),
    )


# ── История ────────────────────────────────────────────────────────

@router.message(F.text == "📜 История")
async def show_history(message: Message) -> None:
    if not await _check_operator(message):
        await message.answer("Недостаточно прав для выполнения действия.")
        return

    async with async_session_factory() as session:
        ticket_service = TicketService(session)
        tickets = await ticket_service.get_operator_history(message.from_user.id)
        await session.commit()

    if not tickets:
        await message.answer("История пуста.")
        return

    await message.answer(
        "📜 История закрытых тикетов:",
        reply_markup=get_operator_history_keyboard(tickets),
    )


# ── Просмотр тикета оператором ─────────────────────────────────────

@router.callback_query(F.data.startswith("op_ticket_"))
async def operator_view_ticket(callback: CallbackQuery) -> None:
    if not await _check_operator_with_log(callback):
        return

    ticket_id = int(callback.data.split("_")[-1])

    async with async_session_factory() as session:
        ticket_service = TicketService(session)
        ticket = await ticket_service.get_by_id(ticket_id)
        messages = await ticket_service.get_ticket_messages(ticket_id)
        await session.commit()

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
async def take_ticket(callback: CallbackQuery) -> None:
    if not await _check_operator_with_log(callback):
        return

    ticket_id = int(callback.data.split("_")[1])

    async with async_session_factory() as session:
        ticket_service = TicketService(session)
        ticket = await ticket_service.assign_operator(ticket_id, callback.from_user.id)
        await session.commit()

    if not ticket:
        await callback.answer("Не удалось взять тикет. Возможно, он уже взят другим оператором.", show_alert=True)
        return

    await callback.message.edit_text(
        f"Вы взяли тикет #{ticket.number} в работу.",
        reply_markup=None,
    )

    # Уведомить пользователя
    from aiogram import Bot
    from config.settings import get_settings
    settings = get_settings()
    bot = Bot(token=settings.bot_token)
    try:
        await bot.send_message(
            ticket.author_id,
            f"Ваше обращение #{ticket.number} взято в работу. Оператор ответит вам в ближайшее время.",
        )
    finally:
        await bot.session.close()

    await callback.answer()


# ── Ответить на тикет ─────────────────────────────────────────────

@router.callback_query(F.data.startswith("reply_"))
async def reply_to_ticket(callback: CallbackQuery, state: FSMContext) -> None:
    if not await _check_operator_with_log(callback):
        return

    ticket_id = int(callback.data.split("_")[1])

    async with async_session_factory() as session:
        ticket_service = TicketService(session)
        ticket = await ticket_service.get_by_id(ticket_id)
        await session.commit()

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
async def send_reply(message: Message, state: FSMContext) -> None:
    if not message.text or len(message.text.strip()) < 1:
        await message.answer("Текст ответа не может быть пустым.")
        return

    data = await state.get_data()
    ticket_id = data.get("ticket_id")

    async with async_session_factory() as session:
        ticket_service = TicketService(session)
        result = await ticket_service.add_message(
            ticket_id=ticket_id,
            sender_id=message.from_user.id,
            text=message.text.strip(),
        )
        await session.commit()

    await state.clear()

    if result:
        ticket = result["ticket"]
        # Уведомить пользователя
        from aiogram import Bot
        from config.settings import get_settings
        settings = get_settings()
        bot = Bot(token=settings.bot_token)
        try:
            await bot.send_message(
                ticket.author_id,
                f"📩 Ответ на обращение #{ticket.number}:\n\n{message.text.strip()}",
            )
        finally:
            await bot.session.close()

    await message.answer(
        "Ответ отправлен пользователю.",
        reply_markup=get_main_menu_operator(),
    )


# ── Закрыть тикет ─────────────────────────────────────────────────

@router.callback_query(F.data.startswith("close_"))
async def close_ticket(callback: CallbackQuery) -> None:
    if not await _check_operator_with_log(callback):
        return

    ticket_id = int(callback.data.split("_")[1])

    async with async_session_factory() as session:
        ticket_service = TicketService(session)
        ticket = await ticket_service.get_by_id(ticket_id)

        if not ticket or ticket.operator_id != callback.from_user.id:
            await callback.answer("Вы не можете закрыть этот тикет.", show_alert=True)
            return

        closed_ticket = await ticket_service.close_ticket(ticket_id, callback.from_user.id)
        await session.commit()

    if not closed_ticket:
        await callback.answer("Не удалось закрыть тикет.", show_alert=True)
        return

    await callback.message.edit_text(
        f"Тикет #{closed_ticket.number} закрыт.",
        reply_markup=None,
    )

    # Уведомить пользователя с просьбой оценить
    from aiogram import Bot
    from config.settings import get_settings
    from bot.keyboards.user import get_rating_keyboard
    settings = get_settings()
    bot = Bot(token=settings.bot_token)
    try:
        await bot.send_message(
            closed_ticket.author_id,
            f"Ваше обращение #{closed_ticket.number} закрыто.\n\nОцените качество ответа:",
            reply_markup=get_rating_keyboard(closed_ticket.id),
        )
    finally:
        await bot.session.close()

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
