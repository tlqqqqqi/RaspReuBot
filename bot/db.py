import aiosqlite

_CREATE_USERS = """
CREATE TABLE IF NOT EXISTS users (
    chat_id             INTEGER PRIMARY KEY,
    selection_key       TEXT,
    selection_name      TEXT,
    morning_enabled     INTEGER NOT NULL DEFAULT 1,
    morning_time        TEXT    NOT NULL DEFAULT '07:00',
    evening_enabled     INTEGER NOT NULL DEFAULT 0,
    evening_time        TEXT    NOT NULL DEFAULT '20:00',
    weekly_enabled      INTEGER NOT NULL DEFAULT 0,
    weekly_time         TEXT    NOT NULL DEFAULT '18:00',
    last_morning_pin_id INTEGER,
    last_evening_pin_id INTEGER,
    created_at          TEXT    DEFAULT (datetime('now')),
    updated_at          TEXT    DEFAULT (datetime('now'))
)
"""

_MIGRATIONS = [
    "ALTER TABLE users ADD COLUMN weekly_enabled INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE users ADD COLUMN weekly_time TEXT NOT NULL DEFAULT '18:00'",
]


async def init_db(db_path: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(_CREATE_USERS)
        for sql in _MIGRATIONS:
            try:
                await db.execute(sql)
            except Exception:
                pass  # column already exists
        await db.commit()


async def get_user(db_path: str, chat_id: int) -> dict | None:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE chat_id = ?", (chat_id,)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def upsert_user(db_path: str, chat_id: int, **fields) -> None:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT chat_id FROM users WHERE chat_id = ?", (chat_id,)
        ) as cur:
            exists = await cur.fetchone()

        if exists is None:
            cols = ["chat_id"] + list(fields.keys())
            vals = [chat_id] + list(fields.values())
            ph = ", ".join("?" * len(vals))
            await db.execute(
                f"INSERT INTO users ({', '.join(cols)}) VALUES ({ph})", vals
            )
        elif fields:
            sets = ", ".join(f"{k} = ?" for k in fields)
            vals = list(fields.values()) + [chat_id]
            await db.execute(
                f"UPDATE users SET {sets}, updated_at = datetime('now') WHERE chat_id = ?",
                vals,
            )
        await db.commit()


async def get_users_for_notification(
    db_path: str, notification_type: str, current_time: str
) -> list[dict]:
    """Return users that should receive a notification at current_time.

    notification_type: 'morning', 'evening', or 'weekly'
    current_time: 'HH:MM'
    """
    enabled_col = f"{notification_type}_enabled"
    time_col = f"{notification_type}_time"
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            f"SELECT * FROM users WHERE selection_key IS NOT NULL"
            f"  AND {enabled_col} = 1 AND {time_col} = ?",
            (current_time,),
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]
