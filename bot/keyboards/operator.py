from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_new_tickets_keyboard(tickets: list) -> InlineKeyboardMarkup:
    buttons = []
    for ticket in tickets:
        text = f"🆕 #{ticket.number} — {_truncate(ticket.text, 30)}"
        buttons.append(
            [InlineKeyboardButton(text=text, callback_data=f"op_ticket_{ticket.id}")]
        )
    buttons.append(
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_operator_active_keyboard(tickets: list) -> InlineKeyboardMarkup:
    buttons = []
    for ticket in tickets:
        status_emoji = _status_emoji(ticket.status)
        text = f"{status_emoji} #{ticket.number} — {_truncate(ticket.text, 30)}"
        buttons.append(
            [InlineKeyboardButton(text=text, callback_data=f"op_ticket_{ticket.id}")]
        )
    buttons.append(
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_operator_history_keyboard(tickets: list) -> InlineKeyboardMarkup:
    buttons = []
    for ticket in tickets[:20]:
        text = f"🔒 #{ticket.number} — {_truncate(ticket.text, 30)}"
        buttons.append(
            [InlineKeyboardButton(text=text, callback_data=f"op_ticket_{ticket.id}")]
        )
    buttons.append(
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_ticket_actions_keyboard(
    ticket_id: int,
    can_take: bool = False,
    can_reply: bool = False,
    can_close: bool = False,
) -> InlineKeyboardMarkup:
    buttons = []

    if can_take:
        buttons.append(
            [InlineKeyboardButton(text="✋ Взять в работу", callback_data=f"take_{ticket_id}")]
        )
    if can_reply:
        buttons.append(
            [InlineKeyboardButton(text="✉ Ответить", callback_data=f"reply_{ticket_id}")]
        )
    if can_close:
        buttons.append(
            [InlineKeyboardButton(text="🔒 Закрыть тикет", callback_data=f"close_{ticket_id}")]
        )

    buttons.append(
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_op_menu")]
    )
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
