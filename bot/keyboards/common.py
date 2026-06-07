from __future__ import annotations

from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from database.models.role import RoleEnum


# ════════════════════════════════════════════════════════════════════
#  ГЛАВНЫЕ МЕНЮ (по ролям)
# ════════════════════════════════════════════════════════════════════

def get_main_menu_user() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(text="❓ Создать обращение")],
        [KeyboardButton(text="📚 FAQ"), KeyboardButton(text="📋 Мои обращения")],
        [KeyboardButton(text="🕐 Передать часы")],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def get_main_menu_operator() -> ReplyKeyboardMarkup:
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
    """Admin main menu — 3 category buttons + user actions."""
    keyboard = [
        [KeyboardButton(text="🛠 Управление"), KeyboardButton(text="📋 Обращения")],
        [KeyboardButton(text="⚙ Настройки")],
        [KeyboardButton(text="❓ Создать обращение")],
        [KeyboardButton(text="📚 FAQ"), KeyboardButton(text="📋 Мои обращения")],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


# ════════════════════════════════════════════════════════════════════
#  ПОДМЕНЮ АДМИНА
# ════════════════════════════════════════════════════════════════════

def get_admin_management_menu() -> ReplyKeyboardMarkup:
    """🛠 Управление — пользователи, категории, FAQ, автоответы."""
    keyboard = [
        [KeyboardButton(text="👥 Пользователи"), KeyboardButton(text="📁 Категории")],
        [KeyboardButton(text="📚 Управление FAQ"), KeyboardButton(text="🤖 Автоответы")],
        [KeyboardButton(text="🔙 В меню")],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def get_admin_tickets_menu() -> ReplyKeyboardMarkup:
    """📋 Обращения — работа с тикетами + выгрузка."""
    keyboard = [
        [KeyboardButton(text="📥 Новые тикеты"), KeyboardButton(text="🛠 В работе")],
        [KeyboardButton(text="📜 История"), KeyboardButton(text="📤 Выгрузка")],
        [KeyboardButton(text="🔙 В меню")],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def get_admin_settings_menu() -> ReplyKeyboardMarkup:
    """⚙ Настройки — табель, быстрые ответы, статистика, очистка."""
    keyboard = [
        [KeyboardButton(text="🕐 Табель"), KeyboardButton(text="⚡ Быстрые ответы")],
        [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="🔧 Настройки бота")],
        [KeyboardButton(text="🧹 Очистка данных")],
        [KeyboardButton(text="🔙 В меню")],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


# ════════════════════════════════════════════════════════════════════
#  УТИЛИТЫ
# ════════════════════════════════════════════════════════════════════

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


def get_main_menu_by_role(role: RoleEnum | str | None) -> ReplyKeyboardMarkup:
    """Return the correct main-menu keyboard for the given role."""
    if role == RoleEnum.ADMIN or role == "admin":
        return get_main_menu_admin()
    if role == RoleEnum.OPERATOR or role == "operator":
        return get_main_menu_operator()
    return get_main_menu_user()
