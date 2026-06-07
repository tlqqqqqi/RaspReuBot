"""Обход капчи как браузер: пройти капчу на HTML-странице, потом XHR.

Через прокси:  REA_PROXY=http://127.0.0.1:10809 .venv/bin/python probe.py
"""
import asyncio
import os
import sqlite3

import aiohttp

BASE = "https://rasp.rea.ru"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
PAGE = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9",
}
XHR = {**PAGE, "X-Requested-With": "XMLHttpRequest", "Referer": BASE + "/"}


def is_captcha(body: str) -> bool:
    return "captcha__title" in body or "не робот" in body


async def get(session, url, headers, proxy, **params):
    async with session.get(
        url, headers=headers, proxy=proxy,
        params=params or None,
        timeout=aiohttp.ClientTimeout(total=25),
    ) as r:
        return r.status, await r.text()


async def main() -> None:
    proxy = os.getenv("REA_PROXY") or None
    print("прокси:", proxy or "нет (напрямую)")
    key = [r[0] for r in sqlite3.connect("bot.db").execute(
        "SELECT selection_key FROM users")][0]
    print("ключ:", repr(key))

    async with aiohttp.ClientSession() as session:
        # --- этап 1: пройти капчу на обычной HTML-странице ---
        page_ok = False
        for i in range(1, 7):
            status, body = await get(session, BASE + "/", PAGE, proxy)
            cap = is_captcha(body)
            print(f"страница, попытка {i}: status={status} len={len(body)} "
                  f"капча={cap} cookies={[c.key for c in session.cookie_jar]}")
            if not cap:
                page_ok = True
                break
            if i == 1:
                await asyncio.sleep(5)
                try:
                    async with session.get(
                        BASE + "/refresh", headers=XHR, proxy=proxy,
                        timeout=aiohttp.ClientTimeout(total=20),
                    ) as r:
                        await r.read()
                        print(f"  GET /refresh -> {r.status} "
                              f"Set-Cookie={r.headers.get('Set-Cookie')}")
                except Exception as e:
                    print(f"  GET /refresh ОШИБКА: {type(e).__name__}: {e}")
            else:
                await asyncio.sleep(3)

        print("страница пройдена:", page_ok)

        # --- этап 2: XHR ScheduleCard в той же сессии ---
        status, body = await get(
            session, BASE + "/Schedule/ScheduleCard", XHR, proxy,
            selection=key, weekNum=-1, catfilter="",
        )
        ok = 'id="weekNum"' in body
        print(f"\nXHR ScheduleCard: status={status} len={len(body)} расписание={ok}")
        print(">>> УСПЕХ" if ok else ">>> всё ещё капча/нет расписания")


if __name__ == "__main__":
    asyncio.run(main())
