from aiogram.fsm.state import State, StatesGroup


class GroupSelection(StatesGroup):
    waiting_for_query = State()


class TimeSelection(StatesGroup):
    waiting_for_morning_time = State()
    waiting_for_evening_time = State()
    waiting_for_weekly_time = State()


class DateInput(StatesGroup):
    waiting_for_date = State()
    waiting_for_range = State()
