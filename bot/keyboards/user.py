from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_category_keyboard(categories: list) -> InlineKeyboardMarkup:
    buttons = []
    for cat in categories:
        buttons.append(
            [InlineKeyboardButton(text=cat.full_name, callback_data=f"cat_{cat.id}")]
        )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_topic_keyboard(topics: list, back_category_id: int | None = None) -> InlineKeyboardMarkup:
    buttons = []
    for topic in topics:
        buttons.append(
            [InlineKeyboardButton(text=topic.full_name, callback_data=f"topic_{topic.id}")]
        )
    if back_category_id is not None:
        buttons.append(
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_categories")]
        )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_user_tickets_keyboard(tickets: list) -> InlineKeyboardMarkup:
    buttons = []
    for ticket in tickets:
        status_emoji = _status_emoji(ticket.status)
        text = f"{status_emoji} #{ticket.number} — {_truncate(ticket.text, 30)}"
        buttons.append(
            [InlineKeyboardButton(text=text, callback_data=f"my_ticket_{ticket.id}")]
        )
    buttons.append(
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_rating_keyboard(ticket_id: int) -> InlineKeyboardMarkup:
    buttons = []
    row = []
    for i in range(1, 6):
        stars = "⭐" * i
        row.append(
            InlineKeyboardButton(text=stars, callback_data=f"rate_{ticket_id}_{i}")
        )
    buttons.append(row)
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_faq_keyboard(faqs: list) -> InlineKeyboardMarkup:
    buttons = []
    for faq in faqs:
        buttons.append(
            [InlineKeyboardButton(text=_truncate(faq.question, 40), callback_data=f"faq_{faq.id}")]
        )
    buttons.append(
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_auto_answer_reply_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="❓ Создать обращение", callback_data="auto_create_ticket")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _status_emoji(status) -> str:
    status_str = status.value if hasattr(status, "value") else str(status)
    mapping = {
        "NEW": "🆕",
        "IN_PROGRESS": "🛠",
        "ANSWERED": "✅",
        "CLOSED": "🔒",
    }
    return mapping.get(status_str, "❓")


def _truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."
