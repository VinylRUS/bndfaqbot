from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from database.models.quick_reply import QuickReply


def get_quick_replies_keyboard(replies: list[QuickReply]) -> InlineKeyboardMarkup:
    buttons = []
    for reply in replies:
        text = _truncate(reply.name, 40)
        buttons.append(
            [InlineKeyboardButton(text=text, callback_data=f"quick_{reply.id}")]
        )
    buttons.append(
        [InlineKeyboardButton(text="➕ Добавить шаблон", callback_data="quick_add")]
    )
    buttons.append(
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_op_menu")]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_quick_reply_detail_keyboard(reply_id: int) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"quick_del_{reply_id}")],
        [InlineKeyboardButton(text="🔙 К списку", callback_data="quick_list")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_save_quick_reply_keyboard(ticket_id: int) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(text="💾 Да", callback_data=f"save_quick_{ticket_id}"),
            InlineKeyboardButton(text="❌ Нет", callback_data=f"nosave_quick_{ticket_id}"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."
