import asyncio
import logging
from datetime import date

import aiohttp
from bs4 import BeautifulSoup
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)

_BASE = "https://rasp.rea.ru"
_HEADERS = {"X-Requested-With": "XMLHttpRequest"}
_sem = asyncio.Semaphore(5)

_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError)),
    reraise=True,
)


@_retry
async def search(session: aiohttp.ClientSession, query: str) -> list[dict]:
    async with _sem:
        async with session.get(
            f"{_BASE}/Schedule/SearchBarSuggestions",
            params={"searchFor": query},
            headers=_HEADERS,
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            resp.raise_for_status()
            data = await resp.json(content_type=None)
            return data if isinstance(data, list) else []


def _parse_details_html(html: str) -> list[dict]:
    """Parse GetDetails response → list of {name, teacher, location} per subgroup."""
    from .parser import SubgroupInfo

    soup = BeautifulSoup(html, "lxml")
    result: list[SubgroupInfo] = []

    for body in soup.select("div.element-info-body"):
        subgroup_name = body.get("data-subgroup", "")

        # Location: "Аудитория: <корпус> - <ауд>\nПлощадка: <площадка>"
        full_text = body.get_text(" ", strip=True)
        location = ""
        if "Аудитория:" in full_text:
            loc_raw = full_text.split("Аудитория:")[1].split("Площадка:")[0].strip()
            loc_raw = loc_raw.strip("-").strip()
            import re
            loc_raw = re.sub(r"\s+", " ", loc_raw)
            loc_raw = re.sub(r"\s*-\s*", " — ", loc_raw)
            location = loc_raw

        # Teacher: <a href="?q=..."> with icon "school"
        teacher = ""
        for link in body.select("a[href^='?q=']"):
            icon = link.find("i", class_="material-icons")
            if icon and icon.get_text(strip=True) == "school":
                icon.decompose()
                teacher = link.get_text(strip=True)
                break

        result.append(SubgroupInfo(name=subgroup_name, teacher=teacher, location=location))

    return result


async def fetch_details(
    session: aiohttp.ClientSession,
    selection_key: str,
    lesson_date: date,
    pair_num: int,
) -> list:
    """Fetch subgroup details for a single lesson.

    Returns list of SubgroupInfo (one per subgroup). Empty list on error.
    """
    date_str = lesson_date.strftime("%d.%m.%Y")
    try:
        async with _sem:
            async with session.get(
                f"{_BASE}/Schedule/GetDetails",
                params={
                    "selection": selection_key,
                    "date": date_str,
                    "timeSlot": pair_num,
                },
                headers=_HEADERS,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    return []
                html = await resp.text()
        return _parse_details_html(html)
    except Exception:
        logger.debug(
            "Could not fetch details for %s pair=%s date=%s", selection_key, pair_num, date_str
        )
        return []


@_retry
async def fetch_week(
    session: aiohttp.ClientSession,
    selection_key: str,
    week_num: int = -1,
) -> str:
    """Fetch schedule HTML for a given week.

    week_num=-1 means current academic week (site default).
    Positive values are absolute academic week numbers.
    """
    async with _sem:
        async with session.get(
            f"{_BASE}/Schedule/ScheduleCard",
            params={
                "selection": selection_key,
                "weekNum": week_num,
                "catfilter": "",
            },
            headers=_HEADERS,
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            resp.raise_for_status()
            return await resp.text()
