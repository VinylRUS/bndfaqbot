from aiogram.fsm.state import State, StatesGroup


class SettingsStates(StatesGroup):
    waiting_user_id = State()
    waiting_role_choice = State()
