from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from . import texts as t


def main_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=t.BTN_TODAY, callback_data="schedule:today")
    kb.button(text=t.BTN_TOMORROW, callback_data="schedule:tomorrow")
    kb.button(text=t.BTN_WEEK, callback_data="schedule:week")
    kb.button(text=t.BTN_BY_DATE, callback_data="schedule:date")
    kb.button(text=t.BTN_BY_RANGE, callback_data="schedule:range")
    kb.button(text=t.BTN_CHANGE_GROUP, callback_data="change_group")
    kb.button(text=t.BTN_SETTINGS, callback_data="settings")
    kb.adjust(2, 1, 2, 2)
    return kb.as_markup()


def settings_menu(
    morning_enabled: bool, evening_enabled: bool, weekly_enabled: bool
) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text=t.BTN_MORNING_ON if morning_enabled else t.BTN_MORNING_OFF,
        callback_data="toggle:morning",
    )
    kb.button(text=t.BTN_SET_MORNING_TIME, callback_data="set_time:morning")
    kb.button(
        text=t.BTN_EVENING_ON if evening_enabled else t.BTN_EVENING_OFF,
        callback_data="toggle:evening",
    )
    kb.button(text=t.BTN_SET_EVENING_TIME, callback_data="set_time:evening")
    kb.button(
        text=t.BTN_WEEKLY_ON if weekly_enabled else t.BTN_WEEKLY_OFF,
        callback_data="toggle:weekly",
    )
    kb.button(text=t.BTN_SET_WEEKLY_TIME, callback_data="set_time:weekly")
    kb.button(text=t.BTN_BACK, callback_data="menu")
    kb.adjust(2, 2, 2, 1)
    return kb.as_markup()


def search_results(results: list[dict]) -> InlineKeyboardMarkup:
    """One button per result (index-based callback_data to avoid 64-byte limit)."""
    kb = InlineKeyboardBuilder()
    for idx, item in enumerate(results[:10]):
        kb.button(text=item["name"][:60], callback_data=f"pick:{idx}")
    kb.button(text="🔍 Другой запрос", callback_data="change_group")
    kb.adjust(1)
    return kb.as_markup()


def cancel_input() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="← Отмена", callback_data="menu")
    return kb.as_markup()
