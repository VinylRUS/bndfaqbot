from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_users_keyboard(users: list, page: int = 0, per_page: int = 10) -> InlineKeyboardMarkup:
    buttons = []
    start = page * per_page
    end = start + per_page
    page_users = users[start:end]

    for user in page_users:
        role_name = _role_display(user.role)
        display = f"{user.display_name} [{role_name}]"
        buttons.append(
            [InlineKeyboardButton(text=display, callback_data=f"admin_user_{user.id}")]
        )

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅ Назад", callback_data=f"users_page_{page - 1}"))
    if end < len(users):
        nav.append(InlineKeyboardButton(text="Вперёд ➡", callback_data=f"users_page_{page + 1}"))
    if nav:
        buttons.append(nav)

    buttons.append(
        [InlineKeyboardButton(text="🔙 В меню", callback_data="back_to_menu")]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_faq_management_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="📋 Список FAQ", callback_data="admin_faq_list")],
        [InlineKeyboardButton(text="➕ Добавить FAQ", callback_data="admin_faq_add")],
        [InlineKeyboardButton(text="🔙 В меню", callback_data="back_to_menu")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_auto_answer_management_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="📋 Список автоответов", callback_data="admin_aa_list")],
        [InlineKeyboardButton(text="➕ Добавить автоответ", callback_data="admin_aa_add")],
        [InlineKeyboardButton(text="🔙 В меню", callback_data="back_to_menu")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_admin_faq_list_keyboard(faqs: list) -> InlineKeyboardMarkup:
    buttons = []
    for faq in faqs:
        status = "✅" if faq.is_active else "❌"
        text = f"{status} {_truncate(faq.question, 35)}"
        buttons.append(
            [InlineKeyboardButton(text=text, callback_data=f"admin_faq_{faq.id}")]
        )
    buttons.append(
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_faq_menu")]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_faq_detail_keyboard(faq_id: int, is_active: bool) -> InlineKeyboardMarkup:
    buttons = []
    buttons.append(
        [InlineKeyboardButton(text="✏ Редактировать", callback_data=f"admin_faq_edit_{faq_id}")]
    )
    toggle_text = "❌ Отключить" if is_active else "✅ Включить"
    buttons.append(
        [InlineKeyboardButton(text=toggle_text, callback_data=f"admin_faq_toggle_{faq_id}")]
    )
    buttons.append(
        [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"admin_faq_del_{faq_id}")]
    )
    buttons.append(
        [InlineKeyboardButton(text="🔙 К списку", callback_data="admin_faq_list")]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_auto_answer_list_keyboard(auto_answers: list) -> InlineKeyboardMarkup:
    buttons = []
    for aa in auto_answers:
        status = "✅" if aa.is_active else "❌"
        text = f"{status} {_truncate(aa.keywords, 35)}"
        buttons.append(
            [InlineKeyboardButton(text=text, callback_data=f"admin_aa_{aa.id}")]
        )
    buttons.append(
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_aa_menu")]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_auto_answer_detail_keyboard(aa_id: int, is_active: bool) -> InlineKeyboardMarkup:
    buttons = []
    buttons.append(
        [InlineKeyboardButton(text="✏ Редактировать", callback_data=f"admin_aa_edit_{aa_id}")]
    )
    toggle_text = "❌ Отключить" if is_active else "✅ Включить"
    buttons.append(
        [InlineKeyboardButton(text=toggle_text, callback_data=f"admin_aa_toggle_{aa_id}")]
    )
    buttons.append(
        [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"admin_aa_del_{aa_id}")]
    )
    buttons.append(
        [InlineKeyboardButton(text="🔙 К списку", callback_data="admin_aa_list")]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_role_change_keyboard(user_id: int) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="👤 Пользователь", callback_data=f"set_role_{user_id}_user")],
        [InlineKeyboardButton(text="🛠 Оператор", callback_data=f"set_role_{user_id}_operator")],
        [InlineKeyboardButton(text="👑 Админ", callback_data=f"set_role_{user_id}_admin")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_users")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _role_display(role) -> str:
    if role is None:
        return "—"
    name = role.name
    if hasattr(name, "value"):
        name = name.value
    mapping = {
        "admin": "👑 Админ",
        "operator": "🛠 Оператор",
        "user": "👤 Пользователь",
    }
    return mapping.get(str(name), str(name))


def _truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."
