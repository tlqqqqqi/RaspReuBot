"""Проверка обхода капчи rasp.rea.ru через прокси: заглушка -> /refresh -> повтор.

Через прокси:  REA_PROXY=http://127.0.0.1:10809 .venv/bin/python probe.py
"""
import asyncio
import os
import sqlite3

import aiohttp

BASE = "https://rasp.rea.ru"
HEADERS = {"X-Requested-With": "XMLHttpRequest"}


async def get_card(session, key, proxy):
    params = {"selection": key, "weekNum": -1, "catfilter": ""}
    async with session.get(
        BASE + "/Schedule/ScheduleCard",
        params=params, headers=HEADERS, proxy=proxy,
        timeout=aiohttp.ClientTimeout(total=20),
    ) as r:
        return r.status, await r.text()


async def main() -> None:
    proxy = os.getenv("REA_PROXY") or None
    print("прокси:", proxy or "нет (напрямую)")
    key = [
        r[0] for r in sqlite3.connect("bot.db").execute(
            "SELECT selection_key FROM users"
        )
    ][0]
    print("ключ:", repr(key))

    async with aiohttp.ClientSession() as session:
        for attempt in range(1, 6):
            status, body = await get_card(session, key, proxy)
            is_sched = 'id="weekNum"' in body
            cookies = [c.key for c in session.cookie_jar]
            print(f"\nпопытка {attempt}: status={status} len={len(body)} "
                  f"расписание={is_sched} cookies={cookies}")

            if is_sched:
                print(">>> УСПЕХ: капча пройдена, расписание получено")
                return

            try:
                async with session.get(
                    BASE + "/refresh", headers=HEADERS, proxy=proxy,
                    timeout=aiohttp.ClientTimeout(total=20),
                ) as r:
                    await r.read()
                    print(f"   GET /refresh -> {r.status} "
                          f"Set-Cookie={r.headers.get('Set-Cookie')}")
            except Exception as e:
                print(f"   GET /refresh ОШИБКА: {type(e).__name__}: {e}")

            await asyncio.sleep(2)

        print(">>> НЕ УДАЛОСЬ пройти капчу за 5 попыток")


if __name__ == "__main__":
    asyncio.run(main())
