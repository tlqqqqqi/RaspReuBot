import logging
import re

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from ..db import get_user, upsert_user
from ..keyboards import cancel_input, main_menu, settings_menu
from ..states import TimeSelection
from .. import texts as t

logger = logging.getLogger(__name__)
router = Router()

_TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


def _settings_text(user: dict) -> str:
    m_line = (
        t.MORNING_ON.format(time=user["morning_time"])
        if user["morning_enabled"]
        else t.MORNING_OFF
    )
    e_line = (
        t.EVENING_ON.format(time=user["evening_time"])
        if user["evening_enabled"]
        else t.EVENING_OFF
    )
    w_line = (
        t.WEEKLY_ON.format(time=user["weekly_time"])
        if user["weekly_enabled"]
        else t.WEEKLY_OFF
    )
    return t.SETTINGS_TITLE.format(morning_line=m_line, evening_line=e_line, weekly_line=w_line)


def _settings_kb(user: dict) -> object:
    return settings_menu(
        bool(user["morning_enabled"]),
        bool(user["evening_enabled"]),
        bool(user["weekly_enabled"]),
    )


@router.callback_query(F.data == "settings")
async def cb_settings(callback: CallbackQuery, db_path: str) -> None:
    user = await get_user(db_path, callback.from_user.id)
    if not user:
        await callback.answer(t.GROUP_NOT_SET, show_alert=True)
        return
    await callback.message.edit_text(
        _settings_text(user), parse_mode="HTML", reply_markup=_settings_kb(user)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("toggle:"))
async def cb_toggle(callback: CallbackQuery, db_path: str) -> None:
    kind = callback.data.split(":")[1]  # "morning", "evening", or "weekly"
    user = await get_user(db_path, callback.from_user.id)
    if not user:
        await callback.answer()
        return

    field = f"{kind}_enabled"
    new_val = 0 if user[field] else 1
    await upsert_user(db_path, callback.from_user.id, **{field: new_val})

    user[field] = new_val
    await callback.message.edit_text(
        _settings_text(user), parse_mode="HTML", reply_markup=_settings_kb(user)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("set_time:"))
async def cb_set_time(callback: CallbackQuery, state: FSMContext) -> None:
    kind = callback.data.split(":")[1]  # "morning", "evening", or "weekly"
    state_map = {
        "morning": TimeSelection.waiting_for_morning_time,
        "evening": TimeSelection.waiting_for_evening_time,
        "weekly": TimeSelection.waiting_for_weekly_time,
    }
    await state.set_state(state_map[kind])
    await callback.message.edit_text(t.ASK_TIME, parse_mode="HTML", reply_markup=cancel_input())
    await callback.answer()


@router.message(TimeSelection.waiting_for_morning_time)
async def handle_morning_time(message: Message, state: FSMContext, db_path: str) -> None:
    await _save_time(message, state, db_path, "morning")


@router.message(TimeSelection.waiting_for_evening_time)
async def handle_evening_time(message: Message, state: FSMContext, db_path: str) -> None:
    await _save_time(message, state, db_path, "evening")


@router.message(TimeSelection.waiting_for_weekly_time)
async def handle_weekly_time(message: Message, state: FSMContext, db_path: str) -> None:
    await _save_time(message, state, db_path, "weekly")


async def _save_time(message: Message, state: FSMContext, db_path: str, kind: str) -> None:
    raw = (message.text or "").strip()
    if not _TIME_RE.match(raw):
        await message.answer(t.TIME_INVALID, parse_mode="HTML")
        return

    await upsert_user(db_path, message.from_user.id, **{f"{kind}_time": raw})
    await state.clear()
    await message.answer(t.TIME_SAVED.format(time=raw), parse_mode="HTML", reply_markup=main_menu())
