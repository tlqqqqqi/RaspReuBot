"""Отправка длинных ответов.

Telegram отбивает сообщения длиннее 4096 символов ошибкой «message is too
long». Расписание за это вылезает регулярно: период на 12 дней ~4.7к символов,
неделя загруженной группы ~5.5к. Раньше такое исключение улетало из хендлера, и
сообщение «Загружаю расписание…» висело вечно.
"""
from aiogram.types import Message

from ..formatter import split_for_telegram


async def edit_long(loading: Message, text: str, reply_markup=None) -> None:
    """Показать text вместо «Загружаю…», добив хвост отдельными сообщениями.

    Клавиатура вешается только на последний кусок, чтобы меню не дублировалось.
    """
    chunks = split_for_telegram(text)
    await loading.edit_text(
        chunks[0], parse_mode="HTML",
        reply_markup=reply_markup if len(chunks) == 1 else None,
    )
    for i, chunk in enumerate(chunks[1:], start=2):
        await loading.answer(
            chunk, parse_mode="HTML",
            reply_markup=reply_markup if i == len(chunks) else None,
        )
