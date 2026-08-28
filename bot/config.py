import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


def site_proxy() -> str | None:
    """HTTP-прокси для запросов к источникам расписания (pleh.tech и rasp.rea.ru).

    И pleh.tech (самохост), и rasp.rea.ru режут датацентровые IP (403 / анти-бот
    заглушка). На VPS запросы к обоим надо гнать через локальный Xray-инбаунд.
    Единый `SITE_PROXY` (напр. http://127.0.0.1:10809) используют оба клиента;
    `REA_PROXY` оставлен как алиас для обратной совместимости. Пусто → напрямую.
    """
    return os.getenv("SITE_PROXY") or os.getenv("REA_PROXY") or None


@dataclass
class Config:
    bot_token: str
    db_path: str
    tz: str


def load_config() -> Config:
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise ValueError("BOT_TOKEN не задан в .env")
    return Config(
        bot_token=token,
        db_path=os.getenv("DB_PATH", "bot.db"),
        tz=os.getenv("TZ", "Europe/Moscow"),
    )
