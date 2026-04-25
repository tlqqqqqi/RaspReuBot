from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date

from bs4 import BeautifulSoup, NavigableString, Tag

logger = logging.getLogger(__name__)


@dataclass
class SubgroupInfo:
    name: str      # "" = вся группа, "Академическая разница" = подгруппа
    teacher: str
    location: str  # реальный кабинет из GetDetails


@dataclass
class Lesson:
    pair_num: int
    time_start: str   # "18:55"
    time_end: str     # "20:25"
    name: str
    lesson_type: str  # "Лекция", "Практическое занятие", …
    location: str     # из карточки (fallback если GetDetails недоступен)
    subgroups: list[SubgroupInfo] = field(default_factory=list)


@dataclass
class Day:
    date: date
    weekday: str        # "ПОНЕДЕЛЬНИК"
    lessons: list[Lesson] = field(default_factory=list)

    @property
    def has_lessons(self) -> bool:
        return bool(self.lessons)


@dataclass
class Week:
    week_num: int
    days: list[Day] = field(default_factory=list)

    def day_by_date(self, target: date) -> Day | None:
        for d in self.days:
            if d.date == target:
                return d
        return None


def _parse_date(header_text: str) -> date | None:
    """'ПОНЕДЕЛЬНИК, 20.04.2026' → date(2026, 4, 20)"""
    try:
        date_str = header_text.split(",")[1].strip()
        day, month, year = date_str.split(".")
        return date(int(year), int(month), int(day))
    except Exception:
        logger.warning("Cannot parse date from: %r", header_text)
        return None


def _parse_slot(slot: Tag) -> Lesson | None:
    if "load-empty" in (slot.get("class") or []):
        return None

    tds = slot.find_all("td", recursive=False)
    if len(tds) < 2:
        return None

    # --- Pair number and times from first <td> ---
    time_td = tds[0]
    pcap = time_td.find("span", class_="pcap")
    pair_num = 0
    if pcap:
        digits = "".join(c for c in pcap.get_text() if c.isdigit())
        pair_num = int(digits) if digits else 0

    time_texts = [
        s.strip()
        for s in time_td.strings
        if s.strip() and "пара" not in s
    ]
    time_start = time_texts[0] if len(time_texts) > 0 else ""
    time_end = time_texts[1] if len(time_texts) > 1 else ""

    # --- Name, type, location from second <td> ---
    a = tds[1].find("a", class_="task")
    if not a:
        return None

    name = ""
    lesson_type = ""
    location_parts: list[str] = []
    after_type = False

    for child in a.children:
        if isinstance(child, NavigableString):
            text = child.strip()
            if not text:
                continue
            if not name:
                name = text
            elif after_type:
                location_parts.append(text)
        elif isinstance(child, Tag):
            if child.name == "i":
                lesson_type = child.get_text(strip=True)
                after_type = True
            elif child.name == "strong":
                location_parts.append(child.get_text(strip=True))

    location = re.sub(r"\s+", " ", " ".join(location_parts)).strip()
    location = re.sub(r"\s*-\s*", " — ", location)
    location = re.sub(r"\s*,\s*", ", ", location)

    return Lesson(
        pair_num=pair_num,
        time_start=time_start,
        time_end=time_end,
        name=name,
        lesson_type=lesson_type,
        location=location,
    )


def parse_html(html: str) -> Week:
    soup = BeautifulSoup(html, "lxml")

    wn_el = soup.find("input", id="weekNum")
    week_num = int(wn_el["value"]) if wn_el else -1

    days: list[Day] = []
    for table in soup.select("table.table"):
        header = table.select_one("th.dayh h5")
        if not header:
            continue
        header_text = header.get_text(strip=True)
        if "," not in header_text:
            continue

        weekday = header_text.split(",")[0].strip()
        day_date = _parse_date(header_text)
        if not day_date:
            continue

        lessons = [
            lesson
            for slot in table.select("tr.slot")
            if (lesson := _parse_slot(slot)) is not None
        ]
        days.append(Day(date=day_date, weekday=weekday, lessons=lessons))

    return Week(week_num=week_num, days=days)
