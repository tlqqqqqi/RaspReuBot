import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


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
