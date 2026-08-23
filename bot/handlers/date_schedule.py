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
from ..states import DateInput
from ._send import edit_long
from .. import provider
from .. import texts as t

logger = logging.getLogger(__name__)
router = Router()

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
        days = await provider.get_days(session, db_path, user, target, target)
        text = format_day(provider.stub_days(days, [target])[0])
        await edit_long(loading, text, main_menu())
    except Exception:
        logger.exception("Failed to fetch date schedule for chat_id=%s", message.from_user.id)
        await loading.edit_text(t.SCHEDULE_ERROR, reply_markup=main_menu())


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
        days = await provider.get_days(session, db_path, user, start, end)
        name = user["selection_name"] or user["selection_key"]
        text = format_range(provider.stub_days(days, dates), name)
        await edit_long(loading, text, main_menu())
    except Exception:
        logger.exception("Failed to fetch range schedule for chat_id=%s", message.from_user.id)
        await loading.edit_text(t.SCHEDULE_ERROR, reply_markup=main_menu())
