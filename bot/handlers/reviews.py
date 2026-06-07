"""Отзывы о преподавателях: меню → поиск → карточка рейтинга → листалка отзывов.

Источник — публичные вьюхи pleh.tech (схема public):
teachers_visible_with_stats (рейтинг) + teacher_reviews_public (тексты).
Логин не нужен. Список отзывов кэшируется в FSM-состоянии на время просмотра.
"""
import logging

import aiohttp
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from .. import pleh_client as pleh
from .. import texts as t
from ..formatter import format_review, format_review_card
from ..keyboards import (
    cancel_input,
    main_menu,
    review_card,
    review_pager,
    review_search_results,
)
from ..states import ReviewSearch

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data == "reviews")
async def cb_reviews_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(ReviewSearch.waiting_for_query)
    await callback.message.edit_text(
        t.REVIEWS_ASK, parse_mode="HTML", reply_markup=cancel_input()
    )
    await callback.answer()


@router.message(ReviewSearch.waiting_for_query)
async def handle_review_query(
    message: Message, state: FSMContext, session: aiohttp.ClientSession
) -> None:
    query = message.text.strip() if message.text else ""
    if not query:
        return
    try:
        found = await pleh.search(session, query)
    except Exception:
        logger.exception("Review search failed for query=%r", query)
        await message.answer(t.SEARCH_ERROR)
        return

    teachers = [r for r in found if r.get("kind") == "teacher"]
    if not teachers:
        await message.answer(t.REVIEWS_EMPTY_SEARCH)
        return

    await state.update_data(review_results=teachers)
    await message.answer(t.REVIEWS_PICK, reply_markup=review_search_results(teachers))


def _render_card(stats: dict) -> tuple[str, object]:
    count = stats.get("review_count") or 0
    if not count:
        text = t.REVIEWS_NO_REVIEWS.format(name=stats.get("full_name") or "Преподаватель")
        return text, review_card(has_reviews=False)
    return format_review_card(stats), review_card(has_reviews=True)


@router.callback_query(F.data.startswith("rv:t:"))
async def cb_pick_teacher(
    callback: CallbackQuery, state: FSMContext, session: aiohttp.ClientSession
) -> None:
    data = await state.get_data()
    results: list[dict] = data.get("review_results", [])
    try:
        idx = int(callback.data.split(":")[2])
        item = results[idx]
    except (IndexError, ValueError):
        await callback.answer(t.REVIEWS_STALE)
        return

    await callback.answer()
    await callback.message.edit_text(t.REVIEWS_LOADING)
    try:
        stats = await pleh.fetch_teacher_stats(session, item["key"], item["name"])
        if stats is None:
            await callback.message.edit_text(
                t.REVIEWS_NO_REVIEWS.format(name=item["name"]),
                parse_mode="HTML",
                reply_markup=review_card(has_reviews=False),
            )
            return
        reviews = []
        if stats.get("review_count"):
            reviews = await pleh.fetch_teacher_reviews(session, stats["id"])
    except Exception:
        logger.exception("Failed to load reviews for %r", item.get("key"))
        await callback.message.edit_text(t.SEARCH_ERROR, reply_markup=main_menu())
        return

    await state.update_data(rv_stats=stats, rv_reviews=reviews)
    text, kb = _render_card(stats)
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data == "rv:card")
async def cb_review_card(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    stats = data.get("rv_stats")
    if not stats:
        await callback.answer(t.REVIEWS_STALE)
        return
    text, kb = _render_card(stats)
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("rv:go:"))
async def cb_review_show(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    reviews: list[dict] = data.get("rv_reviews") or []
    if not reviews:
        await callback.answer(t.REVIEWS_STALE)
        return
    try:
        pos = int(callback.data.split(":")[2])
    except ValueError:
        await callback.answer()
        return
    pos = max(0, min(pos, len(reviews) - 1))

    text = format_review(reviews[pos], pos, len(reviews))
    await callback.message.edit_text(
        text, parse_mode="HTML", reply_markup=review_pager(pos, len(reviews))
    )
    await callback.answer()


@router.callback_query(F.data == "rv:noop")
async def cb_review_noop(callback: CallbackQuery) -> None:
    await callback.answer()
