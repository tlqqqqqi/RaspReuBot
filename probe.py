"""Обход капчи rasp.rea.ru как браузер: ждём -> ОДИН /refresh -> reload'ы.

Через прокси:  REA_PROXY=http://127.0.0.1:10809 .venv/bin/python probe.py
"""
import asyncio
import os
import sqlite3

import aiohttp

BASE = "https://rasp.rea.ru"
HEADERS = {"X-Requested-With": "XMLHttpRequest", "Referer": BASE + "/"}


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
        status, body = await get_card(session, key, proxy)
        if 'id="weekNum"' in body:
            print(f"сразу OK: status={status} len={len(body)} расписание=True")
            print(">>> УСПЕХ (капчи не было)")
            return

        print(f"капча: status={status} len={len(body)}")

        # как браузер: подождать 5с, затем ОДИН раз /refresh
        print("ждём 5с (как setTimeout на странице)...")
        await asyncio.sleep(5)
        try:
            async with session.get(
                BASE + "/refresh", headers=HEADERS, proxy=proxy,
                timeout=aiohttp.ClientTimeout(total=20),
            ) as r:
                await r.read()
                print(f"GET /refresh -> {r.status} "
                      f"Set-Cookie={r.headers.get('Set-Cookie')}")
        except Exception as e:
            print(f"GET /refresh ОШИБКА: {type(e).__name__}: {e}")

        # reload'ы с cookie, БЕЗ повторного /refresh
        for i in range(1, 5):
            await asyncio.sleep(3)
            status, body = await get_card(session, key, proxy)
            ok = 'id="weekNum"' in body
            print(f"reload {i}: status={status} len={len(body)} "
                  f"расписание={ok} cookies={[c.key for c in session.cookie_jar]}")
            if ok:
                print(">>> УСПЕХ: капча пройдена через /refresh")
                return

        print(">>> НЕ УДАЛОСЬ пройти капчу")


if __name__ == "__main__":
    asyncio.run(main())
