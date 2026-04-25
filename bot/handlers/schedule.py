import asyncio
import logging
from datetime import date, timedelta

import aiohttp
from aiogram import F, Router
from aiogram.types import CallbackQuery

from ..db import get_user
from ..formatter import format_day, format_week
from ..keyboards import main_menu
from ..parser import Day, parse_html
from ..rea_client import fetch_details, fetch_week
from .. import texts as t

logger = logging.getLogger(__name__)
router = Router()

_WEEKDAY_NAMES = ["ПОНЕДЕЛЬНИК", "ВТОРНИК", "СРЕДА", "ЧЕТВЕРГ", "ПЯТНИЦА", "СУББОТА", "ВОСКРЕСЕНЬЕ"]


async def _enrich_details(
    session: aiohttp.ClientSession, selection_key: str, days: list[Day]
) -> None:
    """Fetch subgroup details for all lessons in parallel (in-place)."""
    tasks = []
    lessons_flat = []
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


async def _get_day(
    session: aiohttp.ClientSession,
    selection_key: str,
    target: date,
) -> str:
    html = await fetch_week(session, selection_key, week_num=-1)
    week = parse_html(html)
    day = week.day_by_date(target)

    if day is None and week.week_num > 0:
        html2 = await fetch_week(session, selection_key, week_num=week.week_num + 1)
        week2 = parse_html(html2)
        day = week2.day_by_date(target)

    if day is None:
        stub = Day(date=target, weekday=_WEEKDAY_NAMES[target.weekday()], lessons=[])
        return format_day(stub)

    await _enrich_details(session, selection_key, [day])
    return format_day(day)


@router.callback_query(F.data == "schedule:today")
async def cb_today(
    callback: CallbackQuery,
    db_path: str,
    session: aiohttp.ClientSession,
) -> None:
    user = await get_user(db_path, callback.from_user.id)
    if not user or not user["selection_key"]:
        await callback.answer(t.GROUP_NOT_SET, show_alert=True)
        return

    await callback.answer()
    loading_msg = await callback.message.answer(t.SCHEDULE_LOADING)

    try:
        text = await _get_day(session, user["selection_key"], date.today())
    except Exception:
        logger.exception("Failed to fetch today's schedule for chat_id=%s", callback.from_user.id)
        text = t.SCHEDULE_ERROR

    await loading_msg.edit_text(text, parse_mode="HTML", reply_markup=main_menu())


@router.callback_query(F.data == "schedule:tomorrow")
async def cb_tomorrow(
    callback: CallbackQuery,
    db_path: str,
    session: aiohttp.ClientSession,
) -> None:
    user = await get_user(db_path, callback.from_user.id)
    if not user or not user["selection_key"]:
        await callback.answer(t.GROUP_NOT_SET, show_alert=True)
        return

    await callback.answer()
    loading_msg = await callback.message.answer(t.SCHEDULE_LOADING)

    try:
        tomorrow = date.today() + timedelta(days=1)
        text = await _get_day(session, user["selection_key"], tomorrow)
    except Exception:
        logger.exception("Failed to fetch tomorrow's schedule for chat_id=%s", callback.from_user.id)
        text = t.SCHEDULE_ERROR

    await loading_msg.edit_text(text, parse_mode="HTML", reply_markup=main_menu())


@router.callback_query(F.data == "schedule:week")
async def cb_week(
    callback: CallbackQuery,
    db_path: str,
    session: aiohttp.ClientSession,
) -> None:
    user = await get_user(db_path, callback.from_user.id)
    if not user or not user["selection_key"]:
        await callback.answer(t.GROUP_NOT_SET, show_alert=True)
        return

    await callback.answer()
    loading_msg = await callback.message.answer(t.SCHEDULE_LOADING)

    try:
        html = await fetch_week(session, user["selection_key"], week_num=-1)
        week = parse_html(html)
        await _enrich_details(session, user["selection_key"], week.days)
        text = format_week(week, user["selection_name"] or user["selection_key"])
    except Exception:
        logger.exception("Failed to fetch week schedule for chat_id=%s", callback.from_user.id)
        text = t.SCHEDULE_ERROR

    await loading_msg.edit_text(text, parse_mode="HTML", reply_markup=main_menu())
