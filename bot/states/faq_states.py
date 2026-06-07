from aiogram.fsm.state import State, StatesGroup


class FAQManagement(StatesGroup):
    waiting_question = State()
    waiting_answer = State()
    waiting_edit_question = State()
    waiting_edit_answer = State()
