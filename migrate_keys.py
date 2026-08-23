"""Разовая перепривязка пользователей к актуальным ключам pleh.tech.

Берёт сохранённое `selection_name` каждого юзера, ищет его в pleh и переписывает
`selection_key` + `selection_kind` на текущие. Нужно после переезда pleh.tech
на новый бэкенд: старый group_guid может больше не существовать, и тогда бот
молча шлёт «Занятий нет» (ленивый до-резолв срабатывает только при пустом
selection_kind, а не при мёртвом ключе).

По умолчанию — сухой прогон, БД не трогается. Запись только с --apply,
перед записью рядом кладётся резервная копия <db>.bak-<timestamp>.

    .venv/bin/python migrate_keys.py            # показать, что изменится
    .venv/bin/python migrate_keys.py --apply    # применить
    .venv/bin/python migrate_keys.py --db /path/to/bot.db
"""
import argparse
import asyncio
import os
import shutil
import sqlite3
import ssl
from datetime import datetime

import aiohttp
import certifi
from dotenv import load_dotenv

from bot import pleh_client

load_dotenv()


def _fetch_users(db_path: str) -> list[dict]:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            "SELECT chat_id, selection_key, selection_name, selection_kind "
            "FROM users WHERE selection_name IS NOT NULL AND selection_name != ''"
        ).fetchall()
    except sqlite3.OperationalError as e:
        # старая БД без selection_kind — бот добавит колонку на старте
        if "selection_kind" not in str(e):
            raise
        rows = con.execute(
            "SELECT chat_id, selection_key, selection_name, NULL AS selection_kind "
            "FROM users WHERE selection_name IS NOT NULL AND selection_name != ''"
        ).fetchall()
    finally:
        con.close()
    return [dict(r) for r in rows]


async def _resolve(session, name: str) -> tuple[dict | None, str]:
    """Точное совпадение по имени. Возвращает (кандидат, причина отказа)."""
    try:
        found = await pleh_client.search(session, name)
    except Exception as e:
        return None, f"ошибка поиска: {e}"

    low = name.strip().lower()
    exact = [f for f in found if f["name"].strip().lower() == low]
    if not exact:
        near = ", ".join(f["name"] for f in found[:3]) or "ничего"
        return None, f"точного совпадения нет (нашлось: {near})"
    if len(exact) > 1:
        return None, f"неоднозначно: {len(exact)} совпадений"
    return exact[0], ""


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.getenv("DB_PATH", "bot.db"))
    ap.add_argument("--apply", action="store_true", help="записать изменения в БД")
    args = ap.parse_args()

    users = _fetch_users(args.db)
    print(f"БД: {args.db} | пользователей с выбором: {len(users)}")
    print("-" * 60)

    updates: list[tuple[int, str, str, str]] = []  # chat_id, key, kind, name
    unchanged = 0
    failed: list[tuple[int, str, str]] = []

    ctx = ssl.create_default_context(cafile=certifi.where())
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ctx)) as s:
        for u in users:
            name = u["selection_name"]
            match, why = await _resolve(s, name)
            if not match:
                failed.append((u["chat_id"], name, why))
                print(f"✗ {u['chat_id']} {name!r}: {why}")
                continue

            same = (u["selection_key"] == match["key"]
                    and u["selection_kind"] == match["kind"])
            if same:
                unchanged += 1
                print(f"= {u['chat_id']} {name!r}: уже актуален")
            else:
                updates.append((u["chat_id"], match["key"], match["kind"], match["name"]))
                print(f"→ {u['chat_id']} {name!r}: "
                      f"{u['selection_kind']}/{u['selection_key']!r} "
                      f"→ {match['kind']}/{match['key']!r}")

    print("-" * 60)
    print(f"актуальны: {unchanged} | к обновлению: {len(updates)} | не найдено: {len(failed)}")

    if not updates:
        print("менять нечего.")
        return

    if not args.apply:
        print("\nсухой прогон — БД не тронута. Применить: --apply")
        return

    backup = f"{args.db}.bak-{datetime.now():%Y%m%d-%H%M%S}"
    shutil.copy2(args.db, backup)
    print(f"\nрезервная копия: {backup}")

    con = sqlite3.connect(args.db)
    with con:
        # БД могла остаться от версии бота без selection_kind — та же миграция,
        # что делает init_db на старте, иначе UPDATE ниже упадёт.
        cols = [r[1] for r in con.execute("PRAGMA table_info(users)")]
        if "selection_kind" not in cols:
            con.execute("ALTER TABLE users ADD COLUMN selection_kind TEXT")
            print("добавлена колонка selection_kind")
        con.executemany(
            "UPDATE users SET selection_key = ?, selection_kind = ?, "
            "selection_name = ?, updated_at = datetime('now') WHERE chat_id = ?",
            [(key, kind, nm, cid) for cid, key, kind, nm in updates],
        )
    con.close()
    print(f"обновлено записей: {len(updates)}")

    if failed:
        print("\nэтим не нашлось соответствия — им нужно заново выбрать "
              "группу/преподавателя через меню:")
        for cid, name, why in failed:
            print(f"  {cid}: {name!r} — {why}")


if __name__ == "__main__":
    asyncio.run(main())
