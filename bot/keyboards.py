from datetime import date

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from . import texts as t
from .pleh_client import FREE_ROOM_BUILDINGS, PERIOD_TIMES


def main_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=t.BTN_TODAY, callback_data="schedule:today")
    kb.button(text=t.BTN_TOMORROW, callback_data="schedule:tomorrow")
    kb.button(text=t.BTN_WEEK, callback_data="schedule:week")
    kb.button(text=t.BTN_BY_DATE, callback_data="schedule:date")
    kb.button(text=t.BTN_BY_RANGE, callback_data="schedule:range")
    kb.button(text=t.BTN_FREE_ROOMS, callback_data="rooms")
    kb.button(text=t.BTN_CHANGE_GROUP, callback_data="change_group")
    kb.button(text=t.BTN_SETTINGS, callback_data="settings")
    kb.adjust(2, 1, 2, 1, 2)
    return kb.as_markup()


def review_search_results(results: list[dict]) -> InlineKeyboardMarkup:
    """Кнопка на каждого найденного преподавателя (callback rv:t:{idx})."""
    kb = InlineKeyboardBuilder()
    for idx, item in enumerate(results[:10]):
        kb.button(text=item["name"][:60], callback_data=f"rv:t:{idx}")
    kb.button(text="🔍 Другой запрос", callback_data="reviews")
    kb.button(text=t.BTN_MENU, callback_data="menu")
    kb.adjust(1)
    return kb.as_markup()


def review_card(has_reviews: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if has_reviews:
        kb.button(text=t.BTN_SHOW_REVIEWS, callback_data="rv:go:0")
    kb.button(text="🔍 Другой препод", callback_data="reviews")
    kb.button(text=t.BTN_MENU, callback_data="menu")
    kb.adjust(1)
    return kb.as_markup()


def _page_window(pos: int, total: int, size: int = 5) -> list[int]:
    if total <= size:
        return list(range(total))
    start = max(0, min(pos - size // 2, total - size))
    return list(range(start, start + size))


def review_pager(pos: int, total: int) -> InlineKeyboardMarkup:
    """Листалка отзывов: стрелки + быстрый переход по номерам."""
    kb = InlineKeyboardBuilder()
    arrows = 0
    if pos > 0:
        kb.button(text="⬅️", callback_data=f"rv:go:{pos - 1}")
        arrows += 1
    kb.button(text=f"{pos + 1}/{total}", callback_data="rv:noop")
    arrows += 1
    if pos < total - 1:
        kb.button(text="➡️", callback_data=f"rv:go:{pos + 1}")
        arrows += 1

    window = _page_window(pos, total)
    for n in window:
        if n == pos:
            kb.button(text=f"·{n + 1}·", callback_data="rv:noop")
        else:
            kb.button(text=str(n + 1), callback_data=f"rv:go:{n}")

    kb.button(text=t.BTN_TO_RATING, callback_data="rv:card")
    kb.button(text=t.BTN_MENU, callback_data="menu")
    kb.adjust(arrows, len(window), 2)
    return kb.as_markup()


def free_room_buildings() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for idx, building in enumerate(FREE_ROOM_BUILDINGS):
        kb.button(text=building, callback_data=f"rm:b:{idx}")
    kb.button(text=t.BTN_BACK, callback_data="menu")
    kb.adjust(3, 3, 1, 1)
    return kb.as_markup()


def free_room_days(bidx: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=t.BTN_TODAY, callback_data=f"rm:d:{bidx}:today")
    kb.button(text=t.BTN_TOMORROW, callback_data=f"rm:d:{bidx}:tom")
    kb.button(text=t.BTN_BY_DATE, callback_data=f"rm:d:{bidx}:date")
    kb.button(text=t.BTN_BACK, callback_data="rooms")
    kb.adjust(2, 1, 1)
    return kb.as_markup()


def free_room_periods(bidx: int, target: date) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    ymd = target.strftime("%Y%m%d")
    for n in range(1, 9):
        start, _ = PERIOD_TIMES[n]
        kb.button(text=f"{n} пара · {start}", callback_data=f"rm:p:{bidx}:{ymd}:{n}")
    kb.button(text=t.BTN_BACK, callback_data=f"rm:b:{bidx}")
    kb.adjust(2, 2, 2, 2, 1)
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
