"""Клиент к публичному Supabase API проекта pleh.tech.

Отдаёт расписание РЭУ чистым JSON — без капчи и блокировок rasp.rea.ru.
См. память проекта: pleh-tech-supabase-schedule-api.

Возвращает те же дата-классы, что и парсер rasp.rea.ru (Day/Lesson/SubgroupInfo),
поэтому форматтер и хендлеры переиспользуются без изменений.
"""
from __future__ import annotations

import logging
from datetime import date

import aiohttp

from .config import site_proxy
from .parser import Day, Lesson, SubgroupInfo

logger = logging.getLogger(__name__)

# pleh.tech в 2026 съехал со своего проекта на supabase.co на самохост за
# собственным доменом: в бандле база берётся из window.location.origin.
# Старый хост eilpyzysgdyrpunkhosb.supabase.co ещё жив, но вьюхи расписания
# там пустые (200 + []) — бот молча слал «Занятий нет».
_BASE = "https://pleh.tech/rest/v1"
# Анонимный ключ из бандла pleh.tech (role=anon, exp 2036). Ключ и хост меняются
# только парой: старый ключ на новом хосте даёт 401.
# Если протухнет — перевытащить из https://pleh.tech/assets/index-*.js
_ANON = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJyb2xlIjoiYW5vbiIsImlzcyI6InN1cGFiYXNlIiwiaWF0IjoxNzgxNDM2NjY5LCJleHAi"
    "OjIwOTY3OTY2Njl9."
    "uVBH4rCUVsarTmNqhiKBw8kvLqKygVvs31fkWW0C6u0"
)
_HDR = {"apikey": _ANON, "Authorization": f"Bearer {_ANON}"}
# Вьюхи расписания лежат в схеме `api`, не `public`.
_HDR_API = {**_HDR, "Accept-Profile": "api"}

_TIMEOUT = aiohttp.ClientTimeout(total=15)

# Звонки (api.class_periods). Стабильны, совпадают с rasp.rea.ru.
_PERIOD_TIMES: dict[int, tuple[str, str]] = {
    1: ("08:30", "10:00"),
    2: ("10:10", "11:40"),
    3: ("11:50", "13:20"),
    4: ("14:00", "15:30"),
    5: ("15:40", "17:10"),
    6: ("17:20", "18:50"),
    7: ("18:55", "20:25"),
    8: ("20:30", "22:00"),
}

_WEEKDAYS = [
    "ПОНЕДЕЛЬНИК", "ВТОРНИК", "СРЕДА", "ЧЕТВЕРГ",
    "ПЯТНИЦА", "СУББОТА", "ВОСКРЕСЕНЬЕ",
]

# Публичный алиас — нужен форматтеру/клавиатурам для подписи времени пары.
PERIOD_TIMES = _PERIOD_TIMES

# Корпуса со свободными аудиториями (значения совпадают с полем building во
# вьюхе free_slots_current). Стабильны; если pleh добавит корпус — дописать сюда.
FREE_ROOM_BUILDINGS = [
    "1 корпус", "2 корпус", "3 корпус", "4 корпус",
    "6 корпус", "8 корпус", "9 корпус",
]


async def _get(session, path, headers, params):
    # params — список (key, value): допускает повторяющиеся ключи (day=gte&day=lte).
    # proxy — самохост pleh.tech режет датацентровые IP (403); на VPS ходим через Xray.
    async with session.get(
        f"{_BASE}/{path}", params=params, headers=headers,
        proxy=site_proxy(), timeout=_TIMEOUT,
    ) as resp:
        resp.raise_for_status()
        return await resp.json()


async def search(session: aiohttp.ClientSession, query: str) -> list[dict]:
    """Поиск групп и преподавателей по подстроке.

    Возвращает список {name, key, kind, metadata}:
    - kind='group'   → key = group_guid
    - kind='teacher' → key = teacher_slug
    """
    like = f"ilike.*{query}*"
    results: list[dict] = []

    try:
        groups = await _get(
            session, "groups_current", _HDR_API, [
                ("select", "group_guid,group_name"),
                ("group_name", like),
            ],
        )
        for g in sorted(groups, key=lambda g: g["group_name"])[:8]:
            results.append({
                "name": g["group_name"],
                "key": g["group_guid"],
                "kind": "group",
                "metadata": "",
            })
    except Exception:
        logger.exception("pleh: поиск групп не удался для %r", query)

    try:
        teachers = await _get(
            session, "teachers_current", _HDR_API, [
                ("select", "teacher_slug,teacher_name,departments"),
                ("teacher_name", like),
                ("limit", "6"),
            ],
        )
        for tch in teachers:
            deps = tch.get("departments") or []
            # departments может содержать null'ы — отфильтровываем (иначе join падает).
            clean = [d for d in deps if isinstance(d, str) and d.strip()] \
                if isinstance(deps, list) else []
            results.append({
                "name": tch["teacher_name"],
                "key": tch["teacher_slug"],
                "kind": "teacher",
                "metadata": ", ".join(clean),
            })
    except Exception:
        logger.exception("pleh: поиск преподавателей не удался для %r", query)

    return results[:10]


def _format_location(row: dict) -> str:
    building = (row.get("building") or "").strip()
    room = (row.get("room") or "").strip()
    campus = (row.get("campus") or "").strip()
    if building or room:
        loc = " — ".join(p for p in (building, room) if p)
        if campus:
            loc += f", пл. {campus}"
        return loc
    platform = (row.get("platform") or "").strip()
    return platform or "Дистанционно"


def _row_to_lesson(row: dict, is_teacher: bool) -> Lesson:
    period = int(row.get("period") or 0)
    start, end = _PERIOD_TIMES.get(period, ("", ""))
    location = _format_location(row)

    if is_teacher:
        # У препода вместо преподавателя показываем группу.
        group = (row.get("group_name") or "").strip()
        subs = [SubgroupInfo(name="", teacher=f"Группа: {group}" if group else "",
                             location=location)]
    else:
        names = row.get("instructor_names") or []
        teacher = ", ".join(names) if isinstance(names, list) else ""
        sub_name = (row.get("subgroup") or "").strip()
        subs = [SubgroupInfo(name=sub_name, teacher=teacher, location=location)]

    return Lesson(
        pair_num=period,
        time_start=start,
        time_end=end,
        name=(row.get("discipline") or "").strip(),
        lesson_type=(row.get("workload_type") or "").strip(),
        location=location,
        subgroups=subs,
    )


def _rows_to_days(rows: list[dict], is_teacher: bool) -> list[Day]:
    by_day: dict[str, list[dict]] = {}
    for row in rows:
        by_day.setdefault(row["day"], []).append(row)

    days: list[Day] = []
    for day_str in sorted(by_day):
        d = date.fromisoformat(day_str)
        lessons = [
            _row_to_lesson(r, is_teacher)
            for r in sorted(by_day[day_str], key=lambda r: r.get("period") or 0)
        ]
        days.append(Day(date=d, weekday=_WEEKDAYS[d.weekday()], lessons=lessons))
    return days


async def fetch_days(
    session: aiohttp.ClientSession,
    selection_key: str,
    kind: str,
    start: date,
    end: date,
) -> list[Day]:
    """Расписание за период [start, end] для группы или преподавателя.

    Возвращает только дни, в которых есть занятия (как и парсер rasp).
    """
    is_teacher = kind == "teacher"
    if is_teacher:
        view, key_col = "teacher_lessons_current", "teacher_slug"
        select = "day,period,discipline,workload_type,room,building,campus,group_name,subgroup"
    else:
        view, key_col = "lessons_current", "group_guid"
        select = ("day,period,discipline,workload_type,room,building,campus,"
                  "subgroup,instructor_names,platform,resource_url")

    rows = await _get(
        session, view, _HDR_API, [
            ("select", select),
            (key_col, f"eq.{selection_key}"),
            ("day", f"gte.{start.isoformat()}"),
            ("day", f"lte.{end.isoformat()}"),
            ("order", "day.asc,period.asc"),
        ],
    )
    return _rows_to_days(rows, is_teacher)


async def fetch_teacher_stats(
    session: aiohttp.ClientSession, slug: str, name: str = ""
) -> dict | None:
    """Рейтинг преподавателя: {id, full_name, slug, review_count, average_rating}.

    Вьюхи отзывов лежат в схеме `public` (не `api`) — обычный _HDR.
    Если по slug пусто (рассинхрон ключей) — пробуем по полному имени.
    """
    rows = await _get(
        session, "teachers_visible_with_stats", _HDR, [
            ("select", "id,full_name,slug,review_count,average_rating"),
            ("slug", f"eq.{slug}"),
            ("limit", "1"),
        ],
    )
    if not rows and name:
        rows = await _get(
            session, "teachers_visible_with_stats", _HDR, [
                ("select", "id,full_name,slug,review_count,average_rating"),
                ("full_name", f"eq.{name}"),
                ("limit", "1"),
            ],
        )
    return rows[0] if rows else None


async def fetch_teacher_reviews(
    session: aiohttp.ClientSession, teacher_id: str, limit: int = 100
) -> list[dict]:
    """Одобренные отзывы о преподавателе, новые сверху.

    Каждая строка: {overall_rating, review_text, created_at, tags[], criteria[]}.
    """
    return await _get(
        session, "teacher_reviews_public", _HDR, [
            ("select",
             "overall_rating,review_text,created_at,"
             "review_tag_selections(teacher_tags(name)),"
             "review_criteria_ratings(rating,review_criteria(name))"),
            ("teacher_id", f"eq.{teacher_id}"),
            ("order", "created_at.desc"),
            ("limit", str(limit)),
        ],
    )


async def fetch_free_rooms(
    session: aiohttp.ClientSession,
    building: str,
    target: date,
    period: int,
) -> list[dict]:
    """Свободные аудитории корпуса на дату/пару.

    Возвращает строки {room_number, floor, capacity, room_category},
    отсортированные по этажу и номеру. Логин не нужен — вьюха публичная.
    """
    return await _get(
        session, "free_slots_current", _HDR_API, [
            ("select", "room_number,floor,capacity,room_category"),
            ("building", f"eq.{building}"),
            ("date_slot", f"eq.{target.isoformat()}"),
            ("period_number", f"eq.{period}"),
            ("order", "floor.asc,room_number.asc"),
        ],
    )
