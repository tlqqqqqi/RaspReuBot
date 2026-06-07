import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import aiohttp
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest

from .db import get_users_for_notification, upsert_user
from .formatter import format_day, format_week
from .parser import Week
from . import provider

logger = logging.getLogger(__name__)


async def _fetch_day(
    session: aiohttp.ClientSession,
    db_path: str,
    user: dict,
    target: "datetime.date",
) -> str | None:
    """Return formatted day text, or None on error."""
    try:
        days = await provider.get_days(session, db_path, user, target, target)
        day = provider.stub_days(days, [target])[0]
        return format_day(day)
    except Exception:
        logger.exception(
            "Error fetching schedule for chat_id=%s target=%s",
            user.get("chat_id"), target,
        )
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
        except Exception as e:
            logger.warning(
                "Could not unpin msg=%s in chat=%s: %s: %s",
                old_pin_id, chat_id, type(e).__name__, e,
            )

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
        text = await _fetch_day(session, db_path, user, today)
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
        text = await _fetch_day(session, db_path, user, tomorrow)
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

    # Предстоящая неделя: ближайший понедельник .. воскресенье (сегодня вс).
    today = now.date()
    monday = today + timedelta(days=7 - today.weekday())
    week_dates = [monday + timedelta(days=i) for i in range(7)]

    for user in users:
        try:
            days = await provider.get_days(session, db_path, user, monday, week_dates[-1])
            full = provider.stub_days(days, week_dates)
            name = user["selection_name"] or user["selection_key"]
            text = format_week(Week(week_num=0, days=full), name)
        except Exception:
            logger.exception("Error fetching weekly schedule for chat_id=%s", user.get("chat_id"))
            continue

        chat_id = user["chat_id"]
        try:
            await bot.send_message(chat_id, text, parse_mode="HTML")
        except TelegramForbiddenError:
            logger.info("Bot blocked by chat_id=%s, disabling weekly", chat_id)
            await upsert_user(db_path, chat_id, weekly_enabled=0)
        except Exception:
            logger.exception("Failed to send weekly schedule to chat_id=%s", chat_id)
