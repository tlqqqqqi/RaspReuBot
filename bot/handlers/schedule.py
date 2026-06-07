import logging
from datetime import date, timedelta

import aiohttp
from aiogram import F, Router
from aiogram.types import CallbackQuery

from ..db import get_user
from ..formatter import format_day, format_week
from ..keyboards import main_menu
from ..parser import Week
from .. import provider
from .. import texts as t

logger = logging.getLogger(__name__)
router = Router()


async def _get_day(
    session: aiohttp.ClientSession,
    db_path: str,
    user: dict,
    target: date,
) -> str:
    days = await provider.get_days(session, db_path, user, target, target)
    day = provider.stub_days(days, [target])[0]
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
        text = await _get_day(session, db_path, user, date.today())
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
        text = await _get_day(session, db_path, user, tomorrow)
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
        today = date.today()
        monday = today - timedelta(days=today.weekday())
        week_dates = [monday + timedelta(days=i) for i in range(7)]
        days = await provider.get_days(session, db_path, user, monday, week_dates[-1])
        full = provider.stub_days(days, week_dates)
        text = format_week(
            Week(week_num=0, days=full),
            user["selection_name"] or user["selection_key"],
        )
    except Exception:
        logger.exception("Failed to fetch week schedule for chat_id=%s", callback.from_user.id)
        text = t.SCHEDULE_ERROR

    await loading_msg.edit_text(text, parse_mode="HTML", reply_markup=main_menu())
