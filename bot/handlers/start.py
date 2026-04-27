import logging

import aiohttp
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from ..db import get_user, upsert_user
from ..keyboards import cancel_input, main_menu, search_results
from ..rea_client import search
from ..states import GroupSelection
from .. import texts as t

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(t.HELP_TEXT, parse_mode="HTML")


@router.message(Command("start"))
async def cmd_start(
    message: Message,
    state: FSMContext,
    db_path: str,
    session: aiohttp.ClientSession,
) -> None:
    await state.clear()
    user = await get_user(db_path, message.from_user.id)
    await upsert_user(db_path, message.from_user.id)

    if user and user["selection_key"]:
        # Already has a group — show main menu
        await message.answer(t.MAIN_MENU, reply_markup=main_menu())
        return

    await state.set_state(GroupSelection.waiting_for_query)
    await message.answer(t.START_WELCOME)


@router.callback_query(F.data == "change_group")
async def cb_change_group(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    await state.set_state(GroupSelection.waiting_for_query)
    await callback.message.edit_text(t.ASK_GROUP_AGAIN, reply_markup=cancel_input())
    await callback.answer()


@router.message(GroupSelection.waiting_for_query)
async def handle_query(
    message: Message,
    state: FSMContext,
    session: aiohttp.ClientSession,
) -> None:
    query = message.text.strip() if message.text else ""
    if not query:
        return

    try:
        results = await search(session, query)
    except Exception:
        logger.exception("Search failed for query=%r", query)
        await message.answer(t.SEARCH_ERROR)
        return

    if not results:
        await message.answer(t.SEARCH_EMPTY)
        return

    await state.update_data(search_results=results)
    await message.answer(
        t.SEARCH_PICK,
        reply_markup=search_results(results),
    )


@router.callback_query(F.data.startswith("pick:"))
async def cb_pick_result(
    callback: CallbackQuery,
    state: FSMContext,
    db_path: str,
) -> None:
    data = await state.get_data()
    results: list[dict] = data.get("search_results", [])

    try:
        idx = int(callback.data.split(":")[1])
        item = results[idx]
    except (IndexError, ValueError, KeyError):
        await callback.answer("Устаревшая кнопка, попробуй снова.")
        return

    await upsert_user(
        db_path,
        callback.from_user.id,
        selection_key=item["key"],
        selection_name=item["name"],
    )
    await state.clear()

    await callback.message.edit_text(
        t.GROUP_SAVED.format(name=item["name"]),
        parse_mode="HTML",
    )
    await callback.message.answer(t.MAIN_MENU, reply_markup=main_menu())
    await callback.answer()
