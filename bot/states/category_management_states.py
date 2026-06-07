from aiogram.fsm.state import State, StatesGroup


class CategoryManagement(StatesGroup):
    waiting_category_name = State()
    waiting_topic_name = State()
    waiting_edit_name = State()


class TopicManagement(StatesGroup):
    waiting_topic_name = State()
    waiting_edit_name = State()
