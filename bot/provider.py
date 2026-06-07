"""Единая точка доступа к расписанию.

Основной источник — pleh.tech (Supabase, без капчи), запасной — rasp.rea.ru.
Старые пользователи (без selection_kind) лениво до-резолвятся по сохранённому
имени в pleh и обновляются в БД.
"""
from __future__ import annotations

import logging
from datetime import date

import aiohttp

from . import pleh_client, rea_client
from .db import upsert_user
from .parser import Day, parse_html

logger = logging.getLogger(__name__)

_WEEKDAYS = [
    "ПОНЕДЕЛЬНИК", "ВТОРНИК", "СРЕДА", "ЧЕТВЕРГ",
    "ПЯТНИЦА", "СУББОТА", "ВОСКРЕСЕНЬЕ",
]


async def search(session: aiohttp.ClientSession, query: str) -> list[dict]:
    """Поиск групп/преподавателей. pleh основной, rasp fallback.

    Возвращает [{name, key, kind, metadata}]; kind: 'group'|'teacher'|'rea'.
    """
    try:
        results = await pleh_client.search(session, query)
    except Exception:
        logger.exception("provider: pleh search упал для %r", query)
        results = []
    if results:
        return results

    try:
        rea = await rea_client.search(session, query)
    except Exception:
        logger.exception("provider: rea search упал для %r", query)
        return []
    return [
        {"name": r.get("name", ""), "key": r.get("key", ""),
         "kind": "rea", "metadata": r.get("metadata", "")}
        for r in rea
    ]


async def _resolve_legacy(session, name: str) -> dict | None:
    """Старый юзер: по имени находим pleh-ключ (group_guid / teacher_slug)."""
    if not name:
        return None
    try:
        candidates = await pleh_client.search(session, name)
    except Exception:
        return None
    low = name.strip().lower()
    for c in candidates:
        if c["name"].strip().lower() == low:
            return c
    return candidates[0] if candidates else None


async def get_days(
    session: aiohttp.ClientSession,
    db_path: str,
    user: dict,
    start: date,
    end: date,
) -> list[Day]:
    """Дни с занятиями в [start, end]. pleh основной, rasp fallback.

    Бросает исключение, только если оба источника недоступны.
    """
    key = user.get("selection_key") or ""
    kind = user.get("selection_kind")
    name = user.get("selection_name") or ""

    # ленивая миграция старого пользователя на pleh
    if kind not in ("group", "teacher"):
        resolved = await _resolve_legacy(session, name or key)
        if resolved:
            kind, key = resolved["kind"], resolved["key"]
            try:
                await upsert_user(
                    db_path, user["chat_id"],
                    selection_key=key, selection_kind=kind,
                    selection_name=resolved["name"],
                )
            except Exception:
                logger.exception("provider: не смог сохранить миграцию chat_id=%s",
                                 user.get("chat_id"))
            user["selection_key"], user["selection_kind"] = key, kind

    if kind in ("group", "teacher"):
        try:
            return await pleh_client.fetch_days(session, key, kind, start, end)
        except Exception:
            logger.exception("provider: pleh fetch_days упал (key=%r kind=%s), "
                             "пробую rasp", key, kind)

    return await _rea_days(session, name or key, start, end)


async def _rea_days(session, query: str, start: date, end: date) -> list[Day]:
    """Fallback через rasp.rea.ru: дни в диапазоне [start, end]."""
    rkey = query
    try:
        hits = await rea_client.search(session, query)
        if hits:
            rkey = hits[0]["key"]
    except Exception:
        pass

    collected: dict[date, Day] = {}
    seen: set[int] = set()
    wn = -1
    for _ in range(3):  # текущая неделя + до 2 следующих
        html = await rea_client.fetch_week(session, rkey, week_num=wn)
        week = parse_html(html)
        for d in week.days:
            if start <= d.date <= end:
                collected[d.date] = d
        if week.week_num <= 0 or week.week_num in seen:
            break
        seen.add(week.week_num)
        if week.days and week.days[-1].date >= end:
            break
        wn = week.week_num + 1
    return [collected[k] for k in sorted(collected)]


def stub_days(days: list[Day], dates: list[date]) -> list[Day]:
    """По одному Day на каждую дату из dates (пустой, если занятий нет)."""
    by_date = {d.date: d for d in days}
    return [
        by_date.get(dt) or Day(date=dt, weekday=_WEEKDAYS[dt.weekday()], lessons=[])
        for dt in dates
    ]
