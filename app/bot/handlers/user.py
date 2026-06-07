from __future__ import annotations

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from app.database.models.role import RoleEnum
from app.database.models.ticket import TicketStatus
from app.database.session import async_session_factory
from app.services.user_service import UserService
from app.services.ticket_service import TicketService
from app.services.faq_service import FAQService
from app.services.auto_answer_service import AutoAnswerService
from app.services.rating_service import RatingService
from app.services.audit_service import AuditService
from app.database.repositories.category_repo import CategoryRepository
from app.bot.states.ticket_states import TicketCreation
from app.bot.keyboards.common import (
    get_main_menu_user,
    get_cancel_keyboard,
)
from app.bot.keyboards.user import (
    get_category_keyboard,
    get_topic_keyboard,
    get_user_tickets_keyboard,
    get_rating_keyboard,
    get_faq_keyboard,
    get_auto_answer_reply_keyboard,
)


router = Router()


# ── Создать обращение ──────────────────────────────────────────────

@router.message(F.text == "❓ Создать обращение")
async def start_ticket_creation(message: Message, state: FSMContext) -> None:
    async with async_session_factory() as session:
        user_service = UserService(session)
        user = await user_service.get_by_telegram_id(message.from_user.id)
        await session.commit()

    if not user:
        await message.answer("Пожалуйста, нажмите /start для регистрации.")
        return

    role = user.role.name if user.role else RoleEnum.USER
    if hasattr(role, "value"):
        role = RoleEnum(role.value)
    if role not in (RoleEnum.USER, RoleEnum.OPERATOR, RoleEnum.ADMIN):
        await message.answer("Недостаточно прав для выполнения действия.")
        return

    async with async_session_factory() as session:
        cat_repo = CategoryRepository(session)
        categories = await cat_repo.get_roots()
        await session.commit()

    if not categories:
        await message.answer("Категории не настроены. Обратитесь к администратору.")
        return

    await state.set_state(TicketCreation.selecting_category)
    await message.answer(
        "Выберите категорию обращения:",
        reply_markup=get_category_keyboard(categories),
    )


@router.callback_query(TicketCreation.selecting_category, F.data.startswith("cat_"))
async def select_category(callback: CallbackQuery, state: FSMContext) -> None:
    category_id = int(callback.data.split("_")[1])

    async with async_session_factory() as session:
        cat_repo = CategoryRepository(session)
        topics = await cat_repo.get_topics(category_id)
        category = await cat_repo.get_by_id(category_id)
        await session.commit()

    if not topics:
        await state.update_data(category_id=category_id)
        await state.set_state(TicketCreation.entering_text)
        await callback.message.edit_text(
            f"Категория: {category.full_name}\n\nОпишите ваш вопрос:",
            reply_markup=None,
        )
        await callback.message.answer(
            "Введите текст обращения:", reply_markup=get_cancel_keyboard()
        )
        return

    await state.update_data(category_id=category_id)
    await state.set_state(TicketCreation.selecting_topic)
    await callback.message.edit_text(
        f"Категория: {category.full_name}\n\nВыберите тему:",
        reply_markup=get_topic_keyboard(topics, category_id),
    )


@router.callback_query(TicketCreation.selecting_topic, F.data.startswith("topic_"))
async def select_topic(callback: CallbackQuery, state: FSMContext) -> None:
    topic_id = int(callback.data.split("_")[1])

    async with async_session_factory() as session:
        cat_repo = CategoryRepository(session)
        topic = await cat_repo.get_by_id(topic_id)
        await session.commit()

    await state.update_data(category_id=topic_id)
    await state.set_state(TicketCreation.entering_text)
    await callback.message.edit_text(
        f"Тема: {topic.full_name}\n\nОпишите ваш вопрос:",
        reply_markup=None,
    )
    await callback.message.answer(
        "Введите текст обращения:", reply_markup=get_cancel_keyboard()
    )


@router.callback_query(TicketCreation.selecting_category, F.data == "back_to_categories")
async def back_to_categories(callback: CallbackQuery, state: FSMContext) -> None:
    async with async_session_factory() as session:
        cat_repo = CategoryRepository(session)
        categories = await cat_repo.get_roots()
        await session.commit()

    await state.set_state(TicketCreation.selecting_category)
    await callback.message.edit_text(
        "Выберите категорию обращения:",
        reply_markup=get_category_keyboard(categories),
    )


@router.message(TicketCreation.entering_text, F.text == "❌ Отмена")
async def cancel_ticket_creation(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Создание обращения отменено.", reply_markup=get_main_menu_user())


@router.message(TicketCreation.entering_text)
async def enter_ticket_text(message: Message, state: FSMContext) -> None:
    if not message.text or len(message.text.strip()) < 3:
        await message.answer("Текст обращения слишком короткий. Попробуйте ещё раз.")
        return

    data = await state.get_data()
    category_id = data.get("category_id")

    async with async_session_factory() as session:
        ticket_service = TicketService(session)
        ticket = await ticket_service.create_ticket(
            author_id=message.from_user.id,
            category_id=category_id,
            text=message.text.strip(),
        )
        await session.commit()

    await state.clear()
    await message.answer(
        f"Ваше обращение #{ticket.number} создано!\n"
        f"Статус: 🆕 Новое\n\n"
        f"Оператор ответит вам в ближайшее время.",
        reply_markup=get_main_menu_user(),
    )


# ── FAQ ────────────────────────────────────────────────────────────

@router.message(F.text == "📚 FAQ")
async def show_faq_menu(message: Message) -> None:
    async with async_session_factory() as session:
        faq_service = FAQService(session)
        faqs = await faq_service.get_all_active()
        await session.commit()

    if not faqs:
        await message.answer("FAQ пока пуст.")
        return

    from app.bot.keyboards.user import get_faq_keyboard
    await message.answer("Выберите вопрос:", reply_markup=get_faq_keyboard(faqs))


@router.callback_query(F.data.startswith("faq_"))
async def show_faq_answer(callback: CallbackQuery) -> None:
    faq_id = int(callback.data.split("_")[1])

    async with async_session_factory() as session:
        faq_service = FAQService(session)
        faq = await faq_service.get_by_id(faq_id)
        await session.commit()

    if not faq:
        await callback.answer("FAQ не найден.")
        return

    await callback.message.answer(
        f"❓ {faq.question}\n\n{faq.answer}"
    )
    await callback.answer()


# ── Мои обращения ──────────────────────────────────────────────────

@router.message(F.text == "📋 Мои обращения")
async def show_my_tickets(message: Message) -> None:
    async with async_session_factory() as session:
        ticket_service = TicketService(session)
        tickets = await ticket_service.get_user_tickets(message.from_user.id)
        await session.commit()

    if not tickets:
        await message.answer("У вас нет обращений.")
        return

    await message.answer(
        "Ваши обращения:",
        reply_markup=get_user_tickets_keyboard(tickets),
    )


@router.callback_query(F.data.startswith("my_ticket_"))
async def show_ticket_detail(callback: CallbackQuery) -> None:
    ticket_id = int(callback.data.split("_")[-1])

    async with async_session_factory() as session:
        ticket_service = TicketService(session)
        ticket = await ticket_service.get_by_id(ticket_id)
        await session.commit()

    if not ticket:
        await callback.answer("Тикет не найден.")
        return

    if ticket.author_id != callback.from_user.id:
        await callback.answer("Недостаточно прав для выполнения действия.")
        async with async_session_factory() as session:
            audit_service = AuditService(session)
            await audit_service.log_unauthorized_access(
                user_id=callback.from_user.id,
                role=None,
                action=f"view_ticket_{ticket_id}",
            )
            await session.commit()
        return

    text = _format_ticket_detail(ticket)

    async with async_session_factory() as session:
        ticket_service = TicketService(session)
        messages = await ticket_service.get_ticket_messages(ticket_id)
        await session.commit()

    if messages:
        text += "\n\n💬 <b>Переписка:</b>"
        for msg in messages:
            sender = "Вы" if msg.sender_id == callback.from_user.id else "Оператор"
            text += f"\n<b>{sender}:</b> {msg.text}"

    await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()


# ── Оценка качества ────────────────────────────────────────────────

@router.callback_query(F.data.startswith("rate_"))
async def rate_ticket(callback: CallbackQuery) -> None:
    parts = callback.data.split("_")
    ticket_id = int(parts[1])
    score = int(parts[2])

    async with async_session_factory() as session:
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

        await rating_service.create(
            ticket_id=ticket_id,
            user_id=callback.from_user.id,
            score=score,
        )
        await session.commit()

    stars = "⭐" * score
    await callback.message.edit_text(
        f"Спасибо за оценку! {stars}"
    )
    await callback.answer()


# ── Автоответ / создание тикета из автоответа ─────────────────────

@router.callback_query(F.data.startswith("auto_create_ticket_"))
async def auto_create_ticket(callback: CallbackQuery, state: FSMContext) -> None:
    await start_ticket_creation(callback.message, state)
    await callback.answer()


# ── Обработка текстовых сообщений (автоответы) ────────────────────

@router.message(F.text, ~F.text.startswith("/"), ~F.text.startswith("❓"), ~F.text.startswith("📚"), ~F.text.startswith("📋"), ~F.text.startswith("📥"), ~F.text.startswith("🛠"), ~F.text.startswith("📜"), ~F.text.startswith("👥"), ~F.text.startswith("🤖"), ~F.text.startswith("📊"), ~F.text.startswith("📤"), ~F.text.startswith("⚙"), ~F.text.startswith("❌"))
async def handle_free_text(message: Message, state: FSMContext) -> None:
    current_state = await state.get_state()
    if current_state is not None:
        return

    async with async_session_factory() as session:
        auto_answer_service = AutoAnswerService(session)
        match = await auto_answer_service.find_match(message.text)
        await session.commit()

    if match:
        await message.answer(
            match.answer,
            reply_markup=get_auto_answer_reply_keyboard(0),
        )
        return

    await message.answer(
        "Я не нашёл ответа на ваш вопрос. Вы можете:\n"
        "• Создать обращение через кнопку ниже\n"
        "• Посмотреть FAQ\n",
    )


# ── Вспомогательные ───────────────────────────────────────────────

def _format_ticket_detail(ticket) -> str:
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


# ── Назад в меню ──────────────────────────────────────────────────

@router.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    async with async_session_factory() as session:
        user_service = UserService(session)
        user = await user_service.get_by_telegram_id(callback.from_user.id)
        await session.commit()

    if not user:
        await callback.answer("Пожалуйста, нажмите /start")
        return

    role = user.role.name if user.role else RoleEnum.USER
    if hasattr(role, "value"):
        role = RoleEnum(role.value)

    if role == RoleEnum.ADMIN:
        from app.bot.keyboards.common import get_main_menu_admin
        await callback.message.answer("Главное меню 👑", reply_markup=get_main_menu_admin())
    elif role == RoleEnum.OPERATOR:
        from app.bot.keyboards.common import get_main_menu_operator
        await callback.message.answer("Главное меню 🛠", reply_markup=get_main_menu_operator())
    else:
        await callback.message.answer("Главное меню 👤", reply_markup=get_main_menu_user())

    await callback.answer()
