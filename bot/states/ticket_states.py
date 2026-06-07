from aiogram.fsm.state import State, StatesGroup


class TicketCreation(StatesGroup):
    selecting_category = State()
    selecting_topic = State()
    entering_text = State()


class OperatorReply(StatesGroup):
    writing_reply = State()
