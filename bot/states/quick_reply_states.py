from aiogram.fsm.state import State, StatesGroup


class QuickReplyManagement(StatesGroup):
    waiting_name = State()
    waiting_text = State()
