from __future__ import annotations

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.role import RoleEnum
from database.models.ticket import TicketStatus
from database.models.user import User
from services.user_service import UserService
from services.ticket_service import TicketService
from services.faq_service import FAQService
from services.auto_answer_service import AutoAnswerService
from services.rating_service import RatingService
from services.audit_service import AuditService
from database.repositories.category_repo import CategoryRepository
from bot.states.ticket_states import TicketCreation, UserReply
from bot.keyboards.common import (
    get_main_menu_user, get_main_menu_operator, get_main_menu_admin, get_cancel_keyboard,
)
from bot.keyboards.user import (
    get_category_keyboard, get_topic_keyboard, get_user_tickets_keyboard,
    get_rating_keyboard, get_faq_keyboard, get_auto_answer_reply_keyboard,
    get_user_ticket_detail_keyboard,
)


router = Router()


# ── Создать обращение ──────────────────────────────────────────────

@router.message(F.text == "❓ Создать обращение")
async def start_ticket_creation(message: Message, state: FSMContext, **kwargs) -> None:
    db_user: User | None = kwargs.get("db_user")
    if not db_user:
        await message.answer("Пожалуйста, нажмите /start для регистрации.")
        return
    session: AsyncSession = kwargs["db_session"]
    cat_repo = CategoryRepository(session)
    categories = await cat_repo.get_roots()
    if not categories:
        await message.answer("Категории не настроены. Обратитесь к администратору.")
        return
    await state.set_state(TicketCreation.selecting_category)
    await message.answer("Выберите категорию обращения:", reply_markup=get_category_keyboard(categories))


@router.callback_query(TicketCreation.selecting_category, F.data.startswith("cat_"))
async def select_category(callback: CallbackQuery, state: FSMContext, **kwargs) -> None:
    category_id = int(callback.data.split("_")[1])
    session: AsyncSession = kwargs["db_session"]
    cat_repo = CategoryRepository(session)
    topics = await cat_repo.get_topics(category_id)
    category = await cat_repo.get_by_id(category_id)
    if not topics:
        await state.update_data(category_id=category_id)
        await state.set_state(TicketCreation.entering_text)
        await callback.message.edit_text(f"Категория: {category.full_name}\n\nОпишите ваш вопрос:", reply_markup=None)
        await callback.message.answer("Введите текст обращения:", reply_markup=get_cancel_keyboard())
        return
    await state.update_data(category_id=category_id)
    await state.set_state(TicketCreation.selecting_topic)
    await callback.message.edit_text(f"Категория: {category.full_name}\n\nВыберите тему:", reply_markup=get_topic_keyboard(topics, category_id))


@router.callback_query(TicketCreation.selecting_topic, F.data.startswith("topic_"))
async def select_topic(callback: CallbackQuery, state: FSMContext, **kwargs) -> None:
    topic_id = int(callback.data.split("_")[1])
    session: AsyncSession = kwargs["db_session"]
    cat_repo = CategoryRepository(session)
    topic = await cat_repo.get_by_id(topic_id)
    await state.update_data(category_id=topic_id)
    await state.set_state(TicketCreation.entering_text)
    await callback.message.edit_text(f"Тема: {topic.full_name}\n\nОпишите ваш вопрос:", reply_markup=None)
    await callback.message.answer("Введите текст обращения:", reply_markup=get_cancel_keyboard())


@router.callback_query(TicketCreation.selecting_category, F.data == "back_to_categories")
async def back_to_categories(callback: CallbackQuery, state: FSMContext, **kwargs) -> None:
    session: AsyncSession = kwargs["db_session"]
    cat_repo = CategoryRepository(session)
    categories = await cat_repo.get_roots()
    await state.set_state(TicketCreation.selecting_category)
    await callback.message.edit_text("Выберите категорию обращения:", reply_markup=get_category_keyboard(categories))


@router.message(TicketCreation.entering_text, F.text == "❌ Отмена")
async def cancel_ticket_creation(message: Message, state: FSMContext, **kwargs) -> None:
    await state.clear()
    user_role: RoleEnum = kwargs.get("user_role", RoleEnum.USER)
    menu = _get_main_menu_by_role(user_role)
    await message.answer("Создание обращения отменено.", reply_markup=menu())


@router.message(TicketCreation.entering_text)
async def enter_ticket_text(message: Message, state: FSMContext, **kwargs) -> None:
    if not message.text or len(message.text.strip()) < 3:
        await message.answer("Текст обращения слишком короткий. Попробуйте ещё раз.")
        return
    state_data = await state.get_data()
    category_id = state_data.get("category_id")
    session: AsyncSession = kwargs["db_session"]
    ticket_service = TicketService(session)
    ticket = await ticket_service.create_ticket(
        author_id=message.from_user.id, category_id=category_id, text=message.text.strip(),
    )
    await state.clear()
    user_role: RoleEnum = kwargs.get("user_role", RoleEnum.USER)
    menu = _get_main_menu_by_role(user_role)
    await message.answer(
        f"Ваше обращение #{ticket.number} создано!\nСтатус: 🆕 Новое\n\nОператор ответит вам в ближайшее время.",
        reply_markup=menu(),
    )
    # Notify operators and admins
    bot: Bot = kwargs["bot"]
    try:
        user_service = UserService(session)
        operators = await user_service.get_operators()
        admins = await user_service.get_admins()
        notifiable_ids = set()
        for u in operators + admins:
            if u.telegram_id != message.from_user.id:
                notifiable_ids.add(u.telegram_id)
        text_preview = ticket.text[:100] + ("..." if len(ticket.text) > 100 else "")
        notification_text = f"📨 <b>Новое обращение #{ticket.number}</b>\n\nТекст: {text_preview}"
        notification_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👁 Просмотреть", callback_data=f"op_ticket_{ticket.id}")]
        ])
        for tid in notifiable_ids:
            try:
                await bot.send_message(tid, notification_text, parse_mode="HTML", reply_markup=notification_keyboard)
            except Exception:
                pass
    except Exception:
        pass


# ── FAQ ────────────────────────────────────────────────────────────

@router.message(F.text == "📚 FAQ")
async def show_faq_menu(message: Message, **kwargs) -> None:
    session: AsyncSession = kwargs["db_session"]
    faq_service = FAQService(session)
    faqs = await faq_service.get_all_active()
    if not faqs:
        await message.answer("FAQ пока пуст.")
        return
    await message.answer("Выберите вопрос:", reply_markup=get_faq_keyboard(faqs))


@router.callback_query(F.data.startswith("faq_"))
async def show_faq_answer(callback: CallbackQuery, **kwargs) -> None:
    faq_id = int(callback.data.split("_")[1])
    session: AsyncSession = kwargs["db_session"]
    faq_service = FAQService(session)
    faq = await faq_service.get_by_id(faq_id)
    if not faq:
        await callback.answer("FAQ не найден.")
        return
    await callback.message.answer(f"❓ {faq.question}\n\n{faq.answer}")
    await callback.answer()


# ── Мои обращения ──────────────────────────────────────────────────

@router.message(F.text == "📋 Мои обращения")
async def show_my_tickets(message: Message, **kwargs) -> None:
    session: AsyncSession = kwargs["db_session"]
    ticket_service = TicketService(session)
    tickets = await ticket_service.get_user_tickets(message.from_user.id)
    if not tickets:
        await message.answer("У вас нет обращений.")
        return
    await message.answer("Ваши обращения:", reply_markup=get_user_tickets_keyboard(tickets))


@router.callback_query(F.data.startswith("my_ticket_"))
async def show_ticket_detail(callback: CallbackQuery, **kwargs) -> None:
    ticket_id = int(callback.data.split("_")[-1])
    session: AsyncSession = kwargs["db_session"]
    ticket_service = TicketService(session)
    ticket = await ticket_service.get_by_id(ticket_id)
    if not ticket:
        await callback.answer("Тикет не найден.")
        return
    if ticket.author_id != callback.from_user.id:
        await callback.answer("Недостаточно прав для выполнения действия.")
        return
    text = _format_ticket_detail(ticket)
    messages = await ticket_service.get_ticket_messages(ticket_id)
    if messages:
        text += "\n\n💬 <b>Переписка:</b>"
        for msg in messages:
            sender = "Вы" if msg.sender_id == callback.from_user.id else "Оператор"
            content = msg.text or ""
            if msg.file_type == "photo":
                content = "📷 Фото" + (f": {content}" if content else "")
            elif msg.file_type == "document":
                content = "📎 Файл" + (f": {content}" if content else "")
            text += f"\n<b>{sender}:</b> {content}"
    can_reply = ticket.status in (TicketStatus.IN_PROGRESS, TicketStatus.ANSWERED)
    keyboard = get_user_ticket_detail_keyboard(ticket.id, can_reply=can_reply)
    await callback.message.answer(text, parse_mode="HTML", reply_markup=keyboard)
    await callback.answer()


# ── Ответ пользователя на тикет ────────────────────────────────────

@router.callback_query(F.data.startswith("user_reply_"))
async def user_reply_to_ticket(callback: CallbackQuery, state: FSMContext, **kwargs) -> None:
    ticket_id = int(callback.data.split("_")[-1])
    session: AsyncSession = kwargs["db_session"]
    ticket_service = TicketService(session)
    ticket = await ticket_service.get_by_id(ticket_id)
    if not ticket or ticket.author_id != callback.from_user.id:
        await callback.answer("Вы не можете ответить на этот тикет.", show_alert=True)
        return
    if ticket.status not in (TicketStatus.IN_PROGRESS, TicketStatus.ANSWERED):
        await callback.answer("Этот тикет закрыт.", show_alert=True)
        return
    await state.set_state(UserReply.writing_reply)
    await state.update_data(ticket_id=ticket_id)
    await callback.message.answer(
        f"Ответ на тикет #{ticket.number}:\n\nВведите текст сообщения (или фото/документ с подписью):",
        reply_markup=get_cancel_keyboard(),
    )
    await callback.answer()


@router.message(UserReply.writing_reply, F.text == "❌ Отмена")
async def cancel_user_reply(message: Message, state: FSMContext, **kwargs) -> None:
    await state.clear()
    user_role: RoleEnum = kwargs.get("user_role", RoleEnum.USER)
    menu = _get_main_menu_by_role(user_role)
    await message.answer("Ответ отменён.", reply_markup=menu())


@router.message(UserReply.writing_reply, F.text)
async def send_user_reply(message: Message, state: FSMContext, **kwargs) -> None:
    if not message.text or len(message.text.strip()) < 1:
        await message.answer("Текст сообщения не может быть пустым.")
        return
    state_data = await state.get_data()
    ticket_id = state_data.get("ticket_id")
    session: AsyncSession = kwargs["db_session"]
    ticket_service = TicketService(session)
    result = await ticket_service.add_message(
        ticket_id=ticket_id, sender_id=message.from_user.id, text=message.text.strip(),
    )
    await state.clear()
    if not result:
        await message.answer("Не удалось отправить сообщение.")
        return
    ticket = result["ticket"]
    bot: Bot = kwargs["bot"]
    if ticket.operator_id:
        try:
            await bot.send_message(
                ticket.operator_id,
                f"📩 <b>Ответ пользователя</b> на тикет #{ticket.number}:\n\n{message.text.strip()}",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="✉ Ответить", callback_data=f"reply_{ticket_id}")]
                ]),
            )
        except Exception:
            pass
    user_role: RoleEnum = kwargs.get("user_role", RoleEnum.USER)
    menu = _get_main_menu_by_role(user_role)
    await message.answer("Сообщение отправлено оператору.", reply_markup=menu())


@router.message(UserReply.writing_reply, F.photo | F.document)
async def send_user_reply_attachment(message: Message, state: FSMContext, **kwargs) -> None:
    state_data = await state.get_data()
    ticket_id = state_data.get("ticket_id")
    session: AsyncSession = kwargs["db_session"]
    ticket_service = TicketService(session)
    if message.photo:
        file_id = message.photo[-1].file_id
        file_type = "photo"
        caption = message.caption or ""
    elif message.document:
        file_id = message.document.file_id
        file_type = "document"
        caption = message.caption or ""
    else:
        return
    result = await ticket_service.add_message(
        ticket_id=ticket_id, sender_id=message.from_user.id, text=caption,
        file_id=file_id, file_type=file_type,
    )
    await state.clear()
    if result:
        ticket = result["ticket"]
        bot: Bot = kwargs["bot"]
        if ticket.operator_id:
            try:
                if file_type == "photo":
                    await bot.send_photo(ticket.operator_id, photo=file_id, caption=f"📩 Ответ пользователя на тикет #{ticket.number}:\n\n{caption}")
                else:
                    await bot.send_document(ticket.operator_id, document=file_id, caption=f"📩 Ответ пользователя на тикет #{ticket.number}:\n\n{caption}")
            except Exception:
                pass
    user_role: RoleEnum = kwargs.get("user_role", RoleEnum.USER)
    menu = _get_main_menu_by_role(user_role)
    await message.answer("Сообщение с вложением отправлено оператору.", reply_markup=menu())


# ── К списку обращений ─────────────────────────────────────────────

@router.callback_query(F.data == "back_to_my_tickets")
async def back_to_my_tickets(callback: CallbackQuery, **kwargs) -> None:
    session: AsyncSession = kwargs["db_session"]
    ticket_service = TicketService(session)
    tickets = await ticket_service.get_user_tickets(callback.from_user.id)
    if not tickets:
        await callback.message.answer("У вас нет обращений.")
        await callback.answer()
        return
    await callback.message.answer("Ваши обращения:", reply_markup=get_user_tickets_keyboard(tickets))
    await callback.answer()


# ── Оценка качества ────────────────────────────────────────────────

@router.callback_query(F.data.startswith("rate_"))
async def rate_ticket(callback: CallbackQuery, **kwargs) -> None:
    parts = callback.data.split("_")
    ticket_id = int(parts[1])
    score = int(parts[2])
    session: AsyncSession = kwargs["db_session"]
    rating_service = RatingService(session)
    ticket_service = TicketService(session)
    ticket = await ticket_service.get_by_id(ticket_id)
    if not ticket:
        await callback.answer("Тикет не найден.")
        return
    if ticket.author_id != callback.from_user.id:
        await callback.answer("Недостаточно прав для выполнения действия.")
        return
    already_rated = await rating_service.has_rated(ticket_id)
    if already_rated:
        await callback.answer("Вы уже оценили этот тикет.")
        return
    await rating_service.create(ticket_id=ticket_id, user_id=callback.from_user.id, score=score)
    await callback.message.edit_text(f"Спасибо за оценку! {'⭐' * score}")
    await callback.answer()


# ── Автоответ / создание тикета из автоответа ─────────────────────

@router.callback_query(F.data == "auto_create_ticket")
async def auto_create_ticket(callback: CallbackQuery, state: FSMContext, **kwargs) -> None:
    await start_ticket_creation(callback.message, state, **kwargs)
    await callback.answer()


# ── Обработка текстовых сообщений (автоответы) ────────────────────

@router.message(
    F.text,
    ~F.text.startswith("/"),
    ~F.text.startswith("❓"), ~F.text.startswith("📚"), ~F.text.startswith("📋"),
    ~F.text.startswith("📥"), ~F.text.startswith("🛠"), ~F.text.startswith("📜"),
    ~F.text.startswith("👥"), ~F.text.startswith("🤖"), ~F.text.startswith("📊"),
    ~F.text.startswith("📤"), ~F.text.startswith("⚙"), ~F.text.startswith("❌"),
    ~F.text.startswith("🕐"), ~F.text.startswith("📁"), ~F.text.startswith("⚡"),
    StateFilter(None),
)
async def handle_free_text(message: Message, state: FSMContext, **kwargs) -> None:
    session: AsyncSession = kwargs["db_session"]
    auto_answer_service = AutoAnswerService(session)
    match = await auto_answer_service.find_match(message.text)
    if match:
        await message.answer(match.answer, reply_markup=get_auto_answer_reply_keyboard())
        return
    await message.answer("Я не нашёл ответа на ваш вопрос. Вы можете:\n• Создать обращение через кнопку ниже\n• Посмотреть FAQ\n")


# ── Назад в меню ──────────────────────────────────────────────────

@router.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery, state: FSMContext, **kwargs) -> None:
    await state.clear()
    user_role: RoleEnum = kwargs.get("user_role", RoleEnum.USER)
    menu = _get_main_menu_by_role(user_role)
    role_labels = {RoleEnum.ADMIN: "Главное меню 👑", RoleEnum.OPERATOR: "Главное меню 🛠", RoleEnum.USER: "Главное меню 👤"}
    label = role_labels.get(user_role, "Главное меню 👤")
    await callback.message.answer(label, reply_markup=menu())
    await callback.answer()


# ── Вспомогательные ───────────────────────────────────────────────

def _format_ticket_detail(ticket) -> str:
    status_emoji = {"NEW": "🆕", "IN_PROGRESS": "🛠", "ANSWERED": "✅", "CLOSED": "🔒"}
    status_str = ticket.status.value if hasattr(ticket.status, "value") else str(ticket.status)
    emoji = status_emoji.get(status_str, "❓")
    text = (
        f"<b>Тикет #{ticket.number}</b>\n"
        f"Статус: {emoji} {status_str}\n"
        f"Категория: {ticket.category.full_name if ticket.category else '—'}\n"
        f"Дата создания: {ticket.created_at.strftime('%d.%m.%Y %H:%M') if ticket.created_at else '—'}\n"
    )
    if ticket.operator:
        text += f"Оператор: {ticket.operator.display_name}\n"
    if ticket.closed_at:
        text += f"Дата закрытия: {ticket.closed_at.strftime('%d.%m.%Y %H:%M')}\n"
    if ticket.rating:
        text += f"Оценка: {'⭐' * ticket.rating.score}\n"
    text += f"\n<b>Обращение:</b>\n{ticket.text}"
    return text


def _get_main_menu_by_role(role: RoleEnum):
    if role == RoleEnum.ADMIN:
        return get_main_menu_admin
    elif role == RoleEnum.OPERATOR:
        return get_main_menu_operator
    else:
        return get_main_menu_user
