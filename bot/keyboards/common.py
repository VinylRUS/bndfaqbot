from __future__ import annotations

from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)


def get_main_menu_user() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(text="❓ Создать обращение")],
        [KeyboardButton(text="📚 FAQ"), KeyboardButton(text="📋 Мои обращения")],
        [KeyboardButton(text="🕐 Передать часы")],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def get_main_menu_operator() -> ReplyKeyboardMarkup:
    """Operator sees their ticket buttons + user buttons + quick replies."""
    keyboard = [
        [KeyboardButton(text="📥 Новые тикеты")],
        [KeyboardButton(text="🛠 В работе"), KeyboardButton(text="📜 История")],
        [KeyboardButton(text="⚡ Быстрые ответы")],
        [KeyboardButton(text="❓ Создать обращение")],
        [KeyboardButton(text="📚 FAQ"), KeyboardButton(text="📋 Мои обращения")],
        [KeyboardButton(text="🕐 Передать часы")],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def get_main_menu_admin() -> ReplyKeyboardMarkup:
    """Admin sees admin tools + operator buttons + user buttons."""
    keyboard = [
        [KeyboardButton(text="👥 Пользователи"), KeyboardButton(text="📚 Управление FAQ")],
        [KeyboardButton(text="🤖 Автоответы"), KeyboardButton(text="📊 Статистика")],
        [KeyboardButton(text="📥 Новые тикеты"), KeyboardButton(text="🛠 В работе")],
        [KeyboardButton(text="📜 История"), KeyboardButton(text="📤 Выгрузка")],
        [KeyboardButton(text="🕐 Табель"), KeyboardButton(text="📁 Категории")],
        [KeyboardButton(text="⚡ Быстрые ответы")],
        [KeyboardButton(text="❓ Создать обращение"), KeyboardButton(text="⚙ Настройки")],
        [KeyboardButton(text="📚 FAQ"), KeyboardButton(text="📋 Мои обращения")],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def get_back_keyboard(callback_data: str = "back_to_menu") -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(text="🔙 Назад", callback_data=callback_data)]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(text="❌ Отмена")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def get_request_contact_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(text="📱 Отправить номер телефона", request_contact=True)]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
