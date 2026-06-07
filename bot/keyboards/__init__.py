from bot.keyboards.common import (
    get_main_menu_user,
    get_main_menu_operator,
    get_main_menu_admin,
    get_back_keyboard,
    get_cancel_keyboard,
)
from bot.keyboards.user import (
    get_category_keyboard,
    get_topic_keyboard,
    get_user_tickets_keyboard,
    get_rating_keyboard,
    get_faq_keyboard,
)
from bot.keyboards.operator import (
    get_new_tickets_keyboard,
    get_operator_active_keyboard,
    get_operator_history_keyboard,
    get_ticket_actions_keyboard,
)
from bot.keyboards.admin import (
    get_users_keyboard,
    get_faq_management_keyboard,
    get_auto_answer_management_keyboard,
    get_admin_faq_list_keyboard,
    get_auto_answer_list_keyboard,
    get_role_change_keyboard,
)

__all__ = [
    "get_main_menu_user",
    "get_main_menu_operator",
    "get_main_menu_admin",
    "get_back_keyboard",
    "get_cancel_keyboard",
    "get_category_keyboard",
    "get_topic_keyboard",
    "get_user_tickets_keyboard",
    "get_rating_keyboard",
    "get_faq_keyboard",
    "get_new_tickets_keyboard",
    "get_operator_active_keyboard",
    "get_operator_history_keyboard",
    "get_ticket_actions_keyboard",
    "get_users_keyboard",
    "get_faq_management_keyboard",
    "get_auto_answer_management_keyboard",
    "get_admin_faq_list_keyboard",
    "get_auto_answer_list_keyboard",
    "get_role_change_keyboard",
]
