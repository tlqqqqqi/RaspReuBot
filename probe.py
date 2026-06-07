"""Проверка обхода заглушки rasp.rea.ru как браузер.

Шлём браузерные заголовки (User-Agent/Accept/Referer), сначала заходим
на главную за cookie, затем повторяем браузерную схему:
заглушка -> GET /refresh -> перезапрос.

Запуск:  .venv/bin/python probe.py
"""
import asyncio
import sqlite3

import aiohttp

BASE = "https://rasp.rea.ru"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
BROWSER = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
}
XHR = {**BROWSER, "X-Requested-With": "XMLHttpRequest"}


async def get_card(session: aiohttp.ClientSession, key: str):
    params = {"selection": key, "weekNum": -1, "catfilter": ""}
    async with session.get(
        BASE + "/Schedule/ScheduleCard",
        params=params,
        headers=XHR,
        timeout=aiohttp.ClientTimeout(total=20),
    ) as r:
        return r.status, await r.text(), r.headers.get("Set-Cookie")


async def main() -> None:
    key = [
        r[0]
        for r in sqlite3.connect("bot.db").execute(
            "SELECT selection_key FROM users"
        )
    ][0]
    print("ключ для теста:", repr(key))

    async with aiohttp.ClientSession() as session:
        # 1) заходим на главную как браузер — вдруг даст cookie
        try:
            async with session.get(
                BASE + "/", headers=BROWSER,
                timeout=aiohttp.ClientTimeout(total=20),
            ) as r:
                await r.read()
                print("главная:", r.status,
                      "Set-Cookie:", r.headers.get("Set-Cookie"))
        except Exception as e:
            print("главная ОШИБКА:", type(e).__name__, e)
        print("cookies после главной:", [c.key for c in session.cookie_jar])

        # 2) браузерная схема обхода
        for attempt in range(1, 6):
            status, body, setck = await get_card(session, key)
            is_sched = 'id="weekNum"' in body
            print(
                f"\nпопытка {attempt}: status={status} len={len(body)} "
                f"расписание={is_sched}"
            )
            print("   Set-Cookie:", setck)
            print("   cookies в банке:", [c.key for c in session.cookie_jar])

            if is_sched:
                print(">>> УСПЕХ: расписание получено")
                return

            try:
                async with session.get(
                    BASE + "/refresh",
                    headers={**XHR, "Referer": BASE + "/Schedule/ScheduleCard"},
                    timeout=aiohttp.ClientTimeout(total=20),
                ) as r:
                    await r.read()
                    print(f"   GET /refresh -> {r.status}",
                          "Set-Cookie:", r.headers.get("Set-Cookie"))
            except Exception as e:
                print(f"   GET /refresh ОШИБКА: {type(e).__name__}: {e}")

            await asyncio.sleep(2)

        print(">>> НЕ УДАЛОСЬ обойти заглушку за 5 попыток")


if __name__ == "__main__":
    asyncio.run(main())
