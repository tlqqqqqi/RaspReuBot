"""Диагностика: что rasp.rea.ru отдаёт с этого сервера.

Запуск:  .venv/bin/python probe.py
"""
import sqlite3
import urllib.parse
import urllib.request

DB = "bot.db"
URL = "https://rasp.rea.ru/Schedule/ScheduleCard"
HEADERS = {"X-Requested-With": "XMLHttpRequest"}


def fetch(key: str) -> tuple[int, str]:
    params = urllib.parse.urlencode(
        {"selection": key, "weekNum": -1, "catfilter": ""}
    )
    req = urllib.request.Request(URL + "?" + params, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.status, resp.read().decode("utf-8", "replace")


def main() -> None:
    keys = [r[0] for r in sqlite3.connect(DB).execute(
        "SELECT selection_key FROM users"
    )]
    print("ключей в базе:", len(keys))

    for i, key in enumerate(keys):
        try:
            status, body = fetch(key)
        except Exception as e:
            print(f"\nКЛЮЧ {key!r}: ОШИБКА {type(e).__name__}: {e}")
            continue

        is_sched = 'id="weekNum"' in body
        fname = f"dump_{i}.html"
        with open(fname, "w", encoding="utf-8") as f:
            f.write(body)

        print(f"\nКЛЮЧ {key!r}")
        print(f"  status={status} len={len(body)} расписание={is_sched}")
        print(f"  сохранено -> {fname}")
        print("  --- первые 1200 символов ответа ---")
        print(body[:1200])


if __name__ == "__main__":
    main()
