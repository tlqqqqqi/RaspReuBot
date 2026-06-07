"""Тесты обработки анти-бот заглушки rasp.rea.ru. В сеть не ходят."""
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from bot import rea_client
from bot.parser import looks_like_schedule
from bot.rea_client import InterstitialError, fetch_week

FIXTURES = Path(__file__).parent / "fixtures"
SCHEDULE_HTML = (FIXTURES / "week_34_group.html").read_text(encoding="utf-8")
INTERSTITIAL_HTML = (FIXTURES / "interstitial.html").read_text(encoding="utf-8")


class TestLooksLikeSchedule:
    def test_real_schedule_is_recognized(self):
        assert looks_like_schedule(SCHEDULE_HTML) is True

    def test_interstitial_is_rejected(self):
        assert looks_like_schedule(INTERSTITIAL_HTML) is False


@pytest.mark.asyncio
class TestFetchWeekInterstitial:
    async def test_returns_schedule_directly(self):
        with patch.object(
            rea_client, "_fetch_week_once",
            new=AsyncMock(return_value=SCHEDULE_HTML),
        ):
            html = await fetch_week(None, "key", week_num=-1)
        assert looks_like_schedule(html)

    async def test_retries_then_succeeds(self):
        mock = AsyncMock(side_effect=[INTERSTITIAL_HTML, SCHEDULE_HTML])
        with patch.object(rea_client, "_fetch_week_once", new=mock), \
             patch.object(rea_client.asyncio, "sleep", new=AsyncMock()):
            html = await fetch_week(None, "key", week_num=-1)
        assert looks_like_schedule(html)
        assert mock.await_count == 2

    async def test_raises_when_always_interstitial(self):
        mock = AsyncMock(return_value=INTERSTITIAL_HTML)
        with patch.object(rea_client, "_fetch_week_once", new=mock), \
             patch.object(rea_client.asyncio, "sleep", new=AsyncMock()):
            with pytest.raises(InterstitialError):
                await fetch_week(None, "key", week_num=-1)
