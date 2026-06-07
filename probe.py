"""Проверка доступа к rasp.rea.ru (опционально через прокси).

Без прокси:        .venv/bin/python probe.py
Через прокси:      REA_PROXY=http://127.0.0.1:10809 .venv/bin/python probe.py

Печатает по ключу из БД: статус, длину и расписание=True/False.
"""
import asyncio
import os
import sqlite3

import aiohttp

BASE = "https://rasp.rea.ru"
HEADERS = {"X-Requested-With": "XMLHttpRequest"}


async def main() -> None:
    proxy = os.getenv("REA_PROXY") or None
    print("прокси:", proxy or "нет (напрямую)")

    key = [
        r[0]
        for r in sqlite3.connect("bot.db").execute(
            "SELECT selection_key FROM users"
        )
    ][0]
    print("ключ:", repr(key))

    async with aiohttp.ClientSession() as session:
        async with session.get(
            BASE + "/Schedule/ScheduleCard",
            params={"selection": key, "weekNum": -1, "catfilter": ""},
            headers=HEADERS,
            proxy=proxy,
            timeout=aiohttp.ClientTimeout(total=20),
        ) as r:
            body = await r.text()

    is_sched = 'id="weekNum"' in body
    print(f"status={r.status} len={len(body)} расписание={is_sched}")
    if is_sched:
        print(">>> OK: сайт отдал расписание")
    else:
        print(">>> ЗАГЛУШКА: сайт вернул анти-бот страницу")


if __name__ == "__main__":
    asyncio.run(main())
