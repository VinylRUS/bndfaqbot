from aiogram.fsm.state import State, StatesGroup


class AutoAnswerManagement(StatesGroup):
    waiting_keywords = State()
    waiting_answer = State()
    waiting_edit_keywords = State()
    waiting_edit_answer = State()
