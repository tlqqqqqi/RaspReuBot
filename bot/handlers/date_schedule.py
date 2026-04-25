import logging
import re
from datetime import date, timedelta

import aiohttp
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from ..db import get_user
from ..formatter import format_day, format_range
from ..keyboards import cancel_input, main_menu
from ..parser import Day, parse_html
from ..rea_client import fetch_details, fetch_week
from ..states import DateInput
from .. import texts as t

logger = logging.getLogger(__name__)
router = Router()

_WEEKDAY_NAMES = [
    "ПОНЕДЕЛЬНИК", "ВТОРНИК", "СРЕДА", "ЧЕТВЕРГ",
    "ПЯТНИЦА", "СУББОТА", "ВОСКРЕСЕНЬЕ",
]
_DATE_RE = re.compile(r"^(\d{1,2})\.(\d{1,2})(?:\.(\d{4}))?$")


def _parse_single(s: str) -> date | None:
    m = _DATE_RE.match(s.strip())
    if not m:
        return None
    day, month = int(m.group(1)), int(m.group(2))
    year = int(m.group(3)) if m.group(3) else date.today().year
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _parse_range(s: str) -> tuple[date, date] | None:
    # Accept dash variants: -, –, —, with optional spaces
    parts = re.split(r"\s*[-–—]\s*", s.strip(), maxsplit=1)
    if len(parts) != 2:
        return None
    d1 = _parse_single(parts[0])
    d2 = _parse_single(parts[1])
    if d1 is None or d2 is None:
        return None
    if d1 > d2:
        d1, d2 = d2, d1
    return d1, d2


async def _fetch_days(
    session: aiohttp.ClientSession,
    selection_key: str,
    dates: list[date],
) -> list[Day]:
    """Fetch Day objects for each requested date, filling stubs where no lesson data exists."""
    weeks: dict[int, object] = {}

    html = await fetch_week(session, selection_key, week_num=-1)
    base_week = parse_html(html)
    if base_week.week_num > 0:
        weeks[base_week.week_num] = base_week

    ref_date = base_week.days[0].date if base_week.days else date.today()
    ref_wn = base_week.week_num

    result: list[Day] = []
    for target in dates:
        day = None

        for week in weeks.values():
            day = week.day_by_date(target)
            if day:
                break

        if day is None and ref_wn > 0:
            delta = (target - ref_date).days
            for offset in [delta // 7, delta // 7 + 1, delta // 7 - 1]:
                wn = ref_wn + offset
                if wn <= 0:
                    continue
                if wn not in weeks:
                    html2 = await fetch_week(session, selection_key, week_num=wn)
                    w2 = parse_html(html2)
                    if w2.week_num > 0:
                        weeks[w2.week_num] = w2
                day = weeks.get(wn)
                if day is not None:
                    day = day.day_by_date(target)
                if day:
                    break

        if day is None:
            day = Day(date=target, weekday=_WEEKDAY_NAMES[target.weekday()], lessons=[])

        result.append(day)

    return result


async def _enrich(
    session: aiohttp.ClientSession,
    selection_key: str,
    days: list[Day],
) -> None:
    import asyncio
    tasks, lessons_flat = [], []
    for day in days:
        for lesson in day.lessons:
            tasks.append(fetch_details(session, selection_key, day.date, lesson.pair_num))
            lessons_flat.append(lesson)
    if not tasks:
        return
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for lesson, result in zip(lessons_flat, results):
        if isinstance(result, list):
            lesson.subgroups = result


# ── Callbacks that enter FSM ──────────────────────────────────────────────────

@router.callback_query(F.data == "schedule:date")
async def cb_by_date(callback: CallbackQuery, state: FSMContext, db_path: str) -> None:
    user = await get_user(db_path, callback.from_user.id)
    if not user or not user["selection_key"]:
        await callback.answer(t.GROUP_NOT_SET, show_alert=True)
        return
    await state.set_state(DateInput.waiting_for_date)
    await callback.message.edit_text(t.ASK_DATE, parse_mode="HTML", reply_markup=cancel_input())
    await callback.answer()


@router.callback_query(F.data == "schedule:range")
async def cb_by_range(callback: CallbackQuery, state: FSMContext, db_path: str) -> None:
    user = await get_user(db_path, callback.from_user.id)
    if not user or not user["selection_key"]:
        await callback.answer(t.GROUP_NOT_SET, show_alert=True)
        return
    await state.set_state(DateInput.waiting_for_range)
    await callback.message.edit_text(t.ASK_RANGE, parse_mode="HTML", reply_markup=cancel_input())
    await callback.answer()


# ── Message handlers ──────────────────────────────────────────────────────────

@router.message(DateInput.waiting_for_date)
async def handle_date_input(
    message: Message,
    state: FSMContext,
    db_path: str,
    session: aiohttp.ClientSession,
) -> None:
    target = _parse_single(message.text or "")
    if target is None:
        await message.answer(t.DATE_INVALID, parse_mode="HTML")
        return

    user = await get_user(db_path, message.from_user.id)
    if not user or not user["selection_key"]:
        await state.clear()
        await message.answer(t.GROUP_NOT_SET)
        return

    await state.clear()
    loading = await message.answer(t.SCHEDULE_LOADING)

    try:
        days = await _fetch_days(session, user["selection_key"], [target])
        await _enrich(session, user["selection_key"], days)
        text = format_day(days[0])
    except Exception:
        logger.exception("Failed to fetch date schedule for chat_id=%s", message.from_user.id)
        text = t.SCHEDULE_ERROR

    await loading.edit_text(text, parse_mode="HTML", reply_markup=main_menu())


@router.message(DateInput.waiting_for_range)
async def handle_range_input(
    message: Message,
    state: FSMContext,
    db_path: str,
    session: aiohttp.ClientSession,
) -> None:
    parsed = _parse_range(message.text or "")
    if parsed is None:
        await message.answer(t.RANGE_INVALID, parse_mode="HTML")
        return

    start, end = parsed
    if (end - start).days >= 14:
        await message.answer(t.RANGE_TOO_LONG)
        return

    user = await get_user(db_path, message.from_user.id)
    if not user or not user["selection_key"]:
        await state.clear()
        await message.answer(t.GROUP_NOT_SET)
        return

    await state.clear()
    loading = await message.answer(t.SCHEDULE_LOADING)

    dates = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    try:
        days = await _fetch_days(session, user["selection_key"], dates)
        await _enrich(session, user["selection_key"], days)
        name = user["selection_name"] or user["selection_key"]
        text = format_range(days, name)
    except Exception:
        logger.exception("Failed to fetch range schedule for chat_id=%s", message.from_user.id)
        text = t.SCHEDULE_ERROR

    await loading.edit_text(text, parse_mode="HTML", reply_markup=main_menu())
