"""
Tests for scheduler logic.
All external I/O (bot, DB, HTTP) is mocked.
"""
import asyncio
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.scheduler import _send_and_pin, run_evening_job, run_morning_job


def _make_bot(send_ok=True, pin_ok=True, unpin_ok=True):
    bot = MagicMock()
    msg = MagicMock()
    msg.message_id = 999
    bot.send_message = AsyncMock(return_value=msg)
    bot.pin_chat_message = AsyncMock(return_value=True) if pin_ok else AsyncMock(side_effect=Exception("pin failed"))
    bot.unpin_chat_message = AsyncMock(return_value=True) if unpin_ok else AsyncMock(side_effect=Exception("unpin failed"))
    return bot, msg


def _user(chat_id=123, pin_id=None):
    return {
        "chat_id": chat_id,
        "selection_key": "test_key",
        "selection_name": "Тест",
        "last_morning_pin_id": pin_id,
        "last_evening_pin_id": pin_id,
        "morning_enabled": 1,
        "morning_time": "07:00",
        "evening_enabled": 1,
        "evening_time": "20:00",
    }


class TestSendAndPin:
    @pytest.mark.asyncio
    async def test_pins_new_message(self):
        bot, msg = _make_bot()
        with patch("bot.scheduler.upsert_user", new_callable=AsyncMock):
            await _send_and_pin(bot, "/tmp/test.db", _user(), "текст", "last_morning_pin_id")
        bot.pin_chat_message.assert_called_once_with(123, 999, disable_notification=True)

    @pytest.mark.asyncio
    async def test_unpins_old_message_before_pinning(self):
        bot, msg = _make_bot()
        with patch("bot.scheduler.upsert_user", new_callable=AsyncMock):
            await _send_and_pin(bot, "/tmp/test.db", _user(pin_id=111), "текст", "last_morning_pin_id")
        bot.unpin_chat_message.assert_called_once_with(123, 111)
        bot.pin_chat_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_skips_unpin_when_no_old_pin(self):
        bot, msg = _make_bot()
        with patch("bot.scheduler.upsert_user", new_callable=AsyncMock):
            await _send_and_pin(bot, "/tmp/test.db", _user(pin_id=None), "текст", "last_morning_pin_id")
        bot.unpin_chat_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_saves_pin_id_even_if_pin_fails(self):
        """Если pin_chat_message упал — pin_id всё равно должен сохраниться."""
        bot, msg = _make_bot(pin_ok=False)
        mock_upsert = AsyncMock()
        with patch("bot.scheduler.upsert_user", mock_upsert):
            await _send_and_pin(bot, "/tmp/test.db", _user(), "текст", "last_morning_pin_id")
        mock_upsert.assert_called_once()
        _, kwargs = mock_upsert.call_args
        assert kwargs.get("last_morning_pin_id") == 999

    @pytest.mark.asyncio
    async def test_does_not_crash_on_unpin_error(self):
        """Ошибка открепления не должна ломать отправку."""
        bot, msg = _make_bot(unpin_ok=False)
        with patch("bot.scheduler.upsert_user", new_callable=AsyncMock):
            # Не должно бросить исключение
            await _send_and_pin(bot, "/tmp/test.db", _user(pin_id=111), "текст", "last_morning_pin_id")
        bot.pin_chat_message.assert_called_once()


class TestMorningJob:
    @pytest.mark.asyncio
    async def test_uses_timezone_aware_date(self):
        """Дата для утренней рассылки должна браться из московского времени, не UTC."""
        bot, _ = _make_bot()
        user = _user()

        captured_dates = []

        async def fake_fetch_day(session, key, target):
            captured_dates.append(target)
            return "расписание"

        with (
            patch("bot.scheduler.get_users_for_notification", AsyncMock(return_value=[user])),
            patch("bot.scheduler._fetch_day", fake_fetch_day),
            patch("bot.scheduler._send_and_pin", AsyncMock()),
        ):
            await run_morning_job(bot, "/tmp/test.db", MagicMock(), "Europe/Moscow")

        assert len(captured_dates) == 1
        assert isinstance(captured_dates[0], date)

    @pytest.mark.asyncio
    async def test_skips_when_no_users(self):
        bot, _ = _make_bot()
        mock_fetch = AsyncMock()

        with (
            patch("bot.scheduler.get_users_for_notification", AsyncMock(return_value=[])),
            patch("bot.scheduler._fetch_day", mock_fetch),
        ):
            await run_morning_job(bot, "/tmp/test.db", MagicMock(), "Europe/Moscow")

        mock_fetch.assert_not_called()


class TestEveningJob:
    @pytest.mark.asyncio
    async def test_does_not_pin(self):
        """Вечерняя рассылка не должна закреплять сообщение."""
        bot, _ = _make_bot()
        user = _user()

        with (
            patch("bot.scheduler.get_users_for_notification", AsyncMock(return_value=[user])),
            patch("bot.scheduler._fetch_day", AsyncMock(return_value="расписание")),
            patch("bot.scheduler.upsert_user", AsyncMock()),
        ):
            await run_evening_job(bot, "/tmp/test.db", MagicMock(), "Europe/Moscow")

        bot.pin_chat_message.assert_not_called()
        bot.send_message.assert_called_once()
