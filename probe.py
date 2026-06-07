"""Проверка нового источника (pleh.tech) с этого сервера.

Берёт первого пользователя из bot.db, ищет его в pleh по сохранённому имени
и печатает расписание на сегодня. Только чтение, БД не меняет.

Запуск:  .venv/bin/python probe.py
"""
import asyncio
import sqlite3
import ssl
from datetime import date, timedelta

import aiohttp
import certifi

from bot import pleh_client as p
from bot.formatter import format_day
from bot.provider import stub_days


async def main() -> None:
    row = sqlite3.connect("bot.db").execute(
        "SELECT selection_name, selection_key FROM users "
        "WHERE selection_name IS NOT NULL LIMIT 1"
    ).fetchone()
    if not row:
        print("в bot.db нет пользователей с выбором")
        return
    name = row[0]
    print("проверяю по имени:", repr(name))

    ctx = ssl.create_default_context(cafile=certifi.where())
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ctx)) as s:
        found = await p.search(s, name)
        print(f"pleh нашёл вариантов: {len(found)}")
        match = next((f for f in found if f["name"].strip().lower() == name.strip().lower()),
                     found[0] if found else None)
        if not match:
            print(">>> ПУСТО: pleh не нашёл — проверь доступность Supabase с сервера")
            return
        print("совпадение:", match["kind"], "|", match["name"])
        today = date.today()
        days = await p.fetch_days(s, match["key"], match["kind"], today, today + timedelta(days=6))
        print(f">>> OK: pleh отдал {sum(len(d.lessons) for d in days)} занятий за неделю")
        print(format_day(stub_days(days, [today])[0])[:400])


if __name__ == "__main__":
    asyncio.run(main())
