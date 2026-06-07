"""Проверка обхода заглушки rasp.rea.ru через GET /refresh.

Логика повторяет то, что делает браузер на странице "не робот":
получили заглушку -> дёрнули /refresh той же сессией -> перезапросили.

Запуск:  .venv/bin/python probe.py
"""
import asyncio

import aiohttp

import sqlite3

BASE = "https://rasp.rea.ru"
HEADERS = {"X-Requested-With": "XMLHttpRequest"}


async def get_card(session: aiohttp.ClientSession, key: str):
    params = {"selection": key, "weekNum": -1, "catfilter": ""}
    async with session.get(
        BASE + "/Schedule/ScheduleCard",
        params=params,
        headers=HEADERS,
        timeout=aiohttp.ClientTimeout(total=20),
    ) as r:
        return r.status, await r.text()


async def main() -> None:
    key = [
        r[0]
        for r in sqlite3.connect("bot.db").execute(
            "SELECT selection_key FROM users"
        )
    ][0]
    print("ключ для теста:", repr(key))

    async with aiohttp.ClientSession() as session:
        for attempt in range(1, 6):
            status, body = await get_card(session, key)
            is_sched = 'id="weekNum"' in body
            cookies = [c.key for c in session.cookie_jar]
            print(
                f"\nпопытка {attempt}: status={status} len={len(body)} "
                f"расписание={is_sched} cookies={cookies}"
            )

            if is_sched:
                print(">>> УСПЕХ: расписание получено после обхода заглушки")
                return

            # заглушка -> дёргаем /refresh той же сессией, ждём, пробуем снова
            try:
                async with session.get(
                    BASE + "/refresh",
                    headers=HEADERS,
                    timeout=aiohttp.ClientTimeout(total=20),
                ) as r:
                    print(f"   GET /refresh -> status={r.status}")
            except Exception as e:
                print(f"   GET /refresh ОШИБКА: {type(e).__name__}: {e}")

            await asyncio.sleep(2)

        print(">>> НЕ УДАЛОСЬ обойти заглушку за 5 попыток")


if __name__ == "__main__":
    asyncio.run(main())
