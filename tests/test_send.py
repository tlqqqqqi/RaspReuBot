"""Отправка длинных ответов. Без сети и без Telegram — на заглушке Message."""
import asyncio

from bot.handlers._send import edit_long


class FakeMessage:
    def __init__(self):
        self.edited = []   # (текст, клавиатура)
        self.answered = []

    async def edit_text(self, text, parse_mode=None, reply_markup=None):
        self.edited.append((text, reply_markup))

    async def answer(self, text, parse_mode=None, reply_markup=None):
        self.answered.append((text, reply_markup))


def _run(text, markup="MENU"):
    m = FakeMessage()
    asyncio.run(edit_long(m, text, markup))
    return m


class TestEditLong:
    def test_short_text_is_single_edit_with_keyboard(self):
        m = _run("коротко")
        assert m.edited == [("коротко", "MENU")]
        assert m.answered == []

    def test_long_text_is_split_and_keyboard_only_on_last(self):
        days = ["📅 <b>День %d</b>\n\n%s" % (i, "пара\n" * 120) for i in range(12)]
        m = _run("\n\n".join(days))
        sent = m.edited + m.answered
        assert len(sent) > 1, "длинный текст должен разъехаться на несколько сообщений"
        assert m.edited[0][1] is None, "на первом куске меню быть не должно"
        assert all(mk is None for _, mk in m.answered[:-1])
        assert m.answered[-1][1] == "MENU", "меню — только на последнем куске"

    def test_nothing_is_lost(self):
        days = ["📅 <b>День %d</b>\n\n%s" % (i, "пара\n" * 120) for i in range(12)]
        text = "\n\n".join(days)
        m = _run(text)
        assert "\n\n".join(t for t, _ in m.edited + m.answered) == text

    def test_every_piece_fits_telegram_limit(self):
        days = ["📅 <b>День %d</b>\n\n%s" % (i, "пара\n" * 120) for i in range(30)]
        m = _run("\n\n".join(days))
        assert all(len(t) <= 4096 for t, _ in m.edited + m.answered)
