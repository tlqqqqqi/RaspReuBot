"""Свободные аудитории: корпус → день → пара → список (по этажам).

Источник — публичная вьюха pleh.tech free_slots_current (логин не нужен).
Выбор корпуса/дня/пары едет в callback_data, ручной ввод даты — через FSM.
"""
import logging
from datetime import date, timedelta

import aiohttp
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from .. import pleh_client as pleh
from ..formatter import format_free_rooms
from ..keyboards import free_room_buildings, free_room_days, free_room_periods, main_menu
from ..states import RoomDate
from .. import texts as t
from .date_schedule import _parse_single

logger = logging.getLogger(__name__)
router = Router()


def _building(bidx: int) -> str | None:
    if 0 <= bidx < len(pleh.FREE_ROOM_BUILDINGS):
        return pleh.FREE_ROOM_BUILDINGS[bidx]
    return None


@router.callback_query(F.data == "rooms")
async def cb_rooms(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(
        t.ROOMS_PICK_BUILDING, parse_mode="HTML", reply_markup=free_room_buildings()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("rm:b:"))
async def cb_building(callback: CallbackQuery) -> None:
    bidx = int(callback.data.split(":")[2])
    building = _building(bidx)
    if building is None:
        await callback.answer()
        return
    await callback.message.edit_text(
        t.ROOMS_PICK_DAY.format(building=building),
        parse_mode="HTML",
        reply_markup=free_room_days(bidx),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("rm:d:"))
async def cb_day(callback: CallbackQuery, state: FSMContext) -> None:
    _, _, bidx_s, when = callback.data.split(":")
    bidx = int(bidx_s)
    building = _building(bidx)
    if building is None:
        await callback.answer()
        return

    if when == "date":
        await state.set_state(RoomDate.waiting_for_date)
        await state.update_data(bidx=bidx)
        await callback.message.edit_text(t.ROOMS_ASK_DATE, parse_mode="HTML")
        await callback.answer()
        return

    target = date.today() + (timedelta(days=1) if when == "tom" else timedelta())
    await callback.message.edit_text(
        t.ROOMS_PICK_PERIOD.format(building=building, date=target.strftime("%d.%m")),
        parse_mode="HTML",
        reply_markup=free_room_periods(bidx, target),
    )
    await callback.answer()


@router.message(RoomDate.waiting_for_date)
async def handle_room_date(message: Message, state: FSMContext) -> None:
    target = _parse_single(message.text or "")
    if target is None:
        await message.answer(t.ROOMS_ASK_DATE, parse_mode="HTML")
        return
    data = await state.get_data()
    bidx = int(data.get("bidx", -1))
    building = _building(bidx)
    await state.clear()
    if building is None:
        await message.answer(t.MAIN_MENU, reply_markup=main_menu())
        return
    await message.answer(
        t.ROOMS_PICK_PERIOD.format(building=building, date=target.strftime("%d.%m")),
        parse_mode="HTML",
        reply_markup=free_room_periods(bidx, target),
    )


@router.callback_query(F.data.startswith("rm:p:"))
async def cb_period(callback: CallbackQuery, session: aiohttp.ClientSession) -> None:
    _, _, bidx_s, ymd, period_s = callback.data.split(":")
    bidx, period = int(bidx_s), int(period_s)
    building = _building(bidx)
    if building is None:
        await callback.answer()
        return
    target = date(int(ymd[:4]), int(ymd[4:6]), int(ymd[6:8]))

    await callback.answer()
    loading = await callback.message.answer(t.ROOMS_LOADING)
    try:
        rooms = await pleh.fetch_free_rooms(session, building, target, period)
        text = format_free_rooms(building, target, period, rooms)
    except Exception:
        logger.exception(
            "Failed to fetch free rooms building=%s date=%s period=%s",
            building, target, period,
        )
        text = t.SCHEDULE_ERROR
    await loading.edit_text(text, parse_mode="HTML", reply_markup=main_menu())
