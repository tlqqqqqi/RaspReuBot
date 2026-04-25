import asyncio
import logging
from datetime import date, timedelta
from zoneinfo import ZoneInfo

import aiohttp
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest

from .db import get_users_for_notification, upsert_user
from .formatter import format_day, format_week
from .parser import Day, parse_html
from .rea_client import fetch_details, fetch_week
from . import texts as t

logger = logging.getLogger(__name__)


async def _fetch_day(
    session: aiohttp.ClientSession,
    selection_key: str,
    target: date,
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
    if old_pin_id:
        try:
            await bot.unpin_chat_message(chat_id, old_pin_id)
        except TelegramBadRequest:
            pass  # message already deleted or never pinned
        except Exception:
            logger.warning("Could not unpin message %s in chat %s", old_pin_id, chat_id)

    try:
        await bot.pin_chat_message(chat_id, msg.message_id, disable_notification=True)
        await upsert_user(db_path, chat_id, **{pin_field: msg.message_id})
    except Exception:
        logger.warning("Could not pin message %s in chat %s", msg.message_id, chat_id)


async def run_morning_job(
    bot: Bot, db_path: str, session: aiohttp.ClientSession, tz: str
) -> None:
    from datetime import datetime
    current_time = datetime.now(ZoneInfo(tz)).strftime("%H:%M")
    users = await get_users_for_notification(db_path, "morning", current_time)
    if not users:
        return
    logger.info("Morning job: sending to %d users at %s", len(users), current_time)
    for user in users:
        text = await _fetch_day(session, user["selection_key"], date.today())
        if text:
            await _send_and_pin(bot, db_path, user, text, "last_morning_pin_id")


async def run_evening_job(
    bot: Bot, db_path: str, session: aiohttp.ClientSession, tz: str
) -> None:
    from datetime import datetime
    current_time = datetime.now(ZoneInfo(tz)).strftime("%H:%M")
    users = await get_users_for_notification(db_path, "evening", current_time)
    if not users:
        return
    logger.info("Evening job: sending to %d users at %s", len(users), current_time)
    for user in users:
        tomorrow = date.today() + timedelta(days=1)
        text = await _fetch_day(session, user["selection_key"], tomorrow)
        if text:
            await _send_and_pin(bot, db_path, user, text, "last_evening_pin_id")


async def run_weekly_job(
    bot: Bot, db_path: str, session: aiohttp.ClientSession, tz: str
) -> None:
    from datetime import datetime
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
            html = await fetch_week(session, selection_key, week_num=-1)
            current_week = parse_html(html)
            next_wn = current_week.week_num + 1 if current_week.week_num > 0 else -1
            html2 = await fetch_week(session, selection_key, week_num=next_wn)
            next_week = parse_html(html2)

            details = await asyncio.gather(
                *(
                    fetch_details(session, selection_key, day.date, lesson.pair_num)
                    for day in next_week.days
                    for lesson in day.lessons
                ),
                return_exceptions=True,
            )
            lessons_flat = [
                lesson for day in next_week.days for lesson in day.lessons
            ]
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
