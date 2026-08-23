"""Живой smoke-тест источника pleh.tech. По умолчанию пропускается.

Ловит класс «источник переехал/умер, а бот молча шлёт пустое расписание»:
офлайн-тесты маппинга такое не видят — там данные подставлены руками.

Запуск:  RUN_LIVE=1 .venv/bin/pytest tests/test_pleh_live.py -q
"""
import asyncio
import os
import ssl
from datetime import date, timedelta

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("RUN_LIVE"), reason="живой тест: RUN_LIVE=1"
)

# Группа с заведомо непустым расписанием осеннего семестра 2026/27.
_GROUP_NAME = "15.25Д-МФА01/25б"
# Учебный год начинается 04.09.2026 — берём неделю, где пары точно есть.
_WEEK_START = date(2026, 9, 7)


async def _run():
    import aiohttp
    import certifi

    from bot import pleh_client as p

    ctx = ssl.create_default_context(cafile=certifi.where())
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ctx)) as s:
        found = await p.search(s, _GROUP_NAME)
        assert found, f"pleh не нашёл группу {_GROUP_NAME} — источник недоступен?"
        match = next(f for f in found if f["name"] == _GROUP_NAME)
        days = await p.fetch_days(
            s, match["key"], match["kind"], _WEEK_START, _WEEK_START + timedelta(days=6)
        )
        return days


def test_group_week_is_not_empty():
    days = asyncio.run(_run())
    total = sum(len(d.lessons) for d in days)
    assert total > 0, "источник отдал пустую неделю — расписание есть, а бот его не видит"
    assert days[0].lessons[0].name, "у занятия нет названия — сменились поля вьюхи"
