import asyncio
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import aiohttp
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest

from .db import get_users_for_notification, upsert_user
from .formatter import format_day, format_week
from .parser import Day, parse_html
from .rea_client import fetch_details, fetch_week

logger = logging.getLogger(__name__)


async def _fetch_day(
    session: aiohttp.ClientSession,
    selection_key: str,
    target: datetime.date,
) -> str | None:
    """Return formatted day text, or None on error."""
    try:
        html = await fetch_week(session, selection_key, week_num=-1)
        week = parse_html(html)
        day = week.day_by_date(target)

        if day is None and week.week_num > 0:
            html2 = await fetch_week(session, selection_key, week_num=week.week_num + 1)
            week2 = parse_html(html2)
            day = week2.day_by_date(target)

        _WEEKDAYS = ["ПОНЕДЕЛЬНИК", "ВТОРНИК", "СРЕДА", "ЧЕТВЕРГ", "ПЯТНИЦА", "СУББОТА", "ВОСКРЕСЕНЬЕ"]
        if day is None:
            day = Day(date=target, weekday=_WEEKDAYS[target.weekday()], lessons=[])
        else:
            details = await asyncio.gather(
                *(fetch_details(session, selection_key, day.date, l.pair_num) for l in day.lessons),
                return_exceptions=True,
            )
            for lesson, result in zip(day.lessons, details):
                if isinstance(result, list):
                    lesson.subgroups = result
        return format_day(day)
    except Exception:
        logger.exception("Error fetching schedule for key=%r target=%s", selection_key, target)
        return None


async def _send_and_pin(
    bot: Bot,
    db_path: str,
    user: dict,
    text: str,
    pin_field: str,
) -> None:
    chat_id = user["chat_id"]
    try:
        msg = await bot.send_message(chat_id, text, parse_mode="HTML")
    except TelegramForbiddenError:
        logger.info("Bot blocked by chat_id=%s, disabling notifications", chat_id)
        await upsert_user(db_path, chat_id, morning_enabled=0, evening_enabled=0)
        return
    except Exception:
        logger.exception("Failed to send message to chat_id=%s", chat_id)
        return

    old_pin_id = user.get(pin_field)
    logger.debug("Unpin attempt: chat_id=%s field=%s old_pin_id=%s", chat_id, pin_field, old_pin_id)
    if old_pin_id:
        try:
            await bot.unpin_chat_message(chat_id, old_pin_id)
            logger.info("Unpinned msg=%s in chat=%s", old_pin_id, chat_id)
        except TelegramBadRequest:
            pass  # сообщение уже удалено или не было закреплено
        except Exception:
            logger.warning("Could not unpin msg=%s in chat=%s", old_pin_id, chat_id)

    try:
        await bot.pin_chat_message(chat_id, msg.message_id, disable_notification=True)
    except Exception:
        logger.warning("Could not pin msg=%s in chat=%s", msg.message_id, chat_id)

    # Сохраняем pin_id отдельно — даже если pin упал, следующий раз попробует открепить
    try:
        await upsert_user(db_path, chat_id, **{pin_field: msg.message_id})
    except Exception:
        logger.warning("Could not save pin_id for chat_id=%s", chat_id)


async def run_morning_job(
    bot: Bot, db_path: str, session: aiohttp.ClientSession, tz: str
) -> None:
    now = datetime.now(ZoneInfo(tz))
    current_time = now.strftime("%H:%M")
    users = await get_users_for_notification(db_path, "morning", current_time)
    if not users:
        return
    logger.info("Morning job: sending to %d users at %s", len(users), current_time)
    today = now.date()
    for user in users:
        text = await _fetch_day(session, user["selection_key"], today)
        if text:
            await _send_and_pin(bot, db_path, user, text, "last_morning_pin_id")


async def run_evening_job(
    bot: Bot, db_path: str, session: aiohttp.ClientSession, tz: str
) -> None:
    now = datetime.now(ZoneInfo(tz))
    current_time = now.strftime("%H:%M")
    users = await get_users_for_notification(db_path, "evening", current_time)
    if not users:
        return
    logger.info("Evening job: sending to %d users at %s", len(users), current_time)
    tomorrow = now.date() + timedelta(days=1)
    for user in users:
        text = await _fetch_day(session, user["selection_key"], tomorrow)
        if not text:
            continue
        chat_id = user["chat_id"]
        try:
            await bot.send_message(chat_id, text, parse_mode="HTML")
        except TelegramForbiddenError:
            logger.info("Bot blocked by chat_id=%s, disabling evening", chat_id)
            await upsert_user(db_path, chat_id, evening_enabled=0)
        except Exception:
            logger.exception("Failed to send evening message to chat_id=%s", chat_id)


async def run_weekly_job(
    bot: Bot, db_path: str, session: aiohttp.ClientSession, tz: str
) -> None:
    now = datetime.now(ZoneInfo(tz))
    if now.weekday() != 6:  # только воскресенье
        return

    current_time = now.strftime("%H:%M")
    users = await get_users_for_notification(db_path, "weekly", current_time)
    if not users:
        return
    logger.info("Weekly job: sending to %d users at %s", len(users), current_time)

    for user in users:
        selection_key = user["selection_key"]
        try:
            # В воскресенье week_num=-1 уже отдаёт предстоящую неделю
            html = await fetch_week(session, selection_key, week_num=-1)
            next_week = parse_html(html)

            details = await asyncio.gather(
                *(
                    fetch_details(session, selection_key, day.date, lesson.pair_num)
                    for day in next_week.days
                    for lesson in day.lessons
                ),
                return_exceptions=True,
            )
            lessons_flat = [lesson for day in next_week.days for lesson in day.lessons]
            for lesson, result in zip(lessons_flat, details):
                if isinstance(result, list):
                    lesson.subgroups = result

            name = user["selection_name"] or selection_key
            text = format_week(next_week, name)
        except Exception:
            logger.exception("Error fetching weekly schedule for key=%r", selection_key)
            continue

        chat_id = user["chat_id"]
        try:
            await bot.send_message(chat_id, text, parse_mode="HTML")
        except TelegramForbiddenError:
            logger.info("Bot blocked by chat_id=%s, disabling weekly", chat_id)
            await upsert_user(db_path, chat_id, weekly_enabled=0)
        except Exception:
            logger.exception("Failed to send weekly schedule to chat_id=%s", chat_id)
