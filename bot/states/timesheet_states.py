from aiogram.fsm.state import State, StatesGroup


class TimesheetStates(StatesGroup):
    # Admin: create period
    choosing_month = State()
    choosing_start_day = State()
    choosing_end_day = State()
    choosing_employee_type = State()

    # User: submit hours
    selecting_period = State()
    entering_hours = State()

    # Admin: Google settings
    entering_spreadsheet_id = State()
    entering_credentials_json = State()

    # Admin: manage employee properties
    selecting_employee = State()
    choosing_employee_type = State()
    entering_workplace = State()
    entering_full_name = State()
