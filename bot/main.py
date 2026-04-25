import asyncio
import logging
import ssl

import aiohttp
import certifi
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .config import load_config
from .db import init_db
from .handlers import date_schedule, menu, schedule, settings, start
from .scheduler import run_evening_job, run_morning_job, run_weekly_job

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    config = load_config()

    await init_db(config.db_path)

    bot = Bot(token=config.bot_token)
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(start.router)
    dp.include_router(menu.router)
    dp.include_router(schedule.router)
    dp.include_router(date_schedule.router)
    dp.include_router(settings.router)

    scheduler = AsyncIOScheduler(timezone=config.tz)

    ssl_ctx = ssl.create_default_context(cafile=certifi.where())
    connector = aiohttp.TCPConnector(ssl=ssl_ctx)
    async with aiohttp.ClientSession(connector=connector) as session:
        scheduler.add_job(
            run_morning_job,
            "cron",
            minute="*",
            kwargs={"bot": bot, "db_path": config.db_path, "session": session, "tz": config.tz},
        )
        scheduler.add_job(
            run_evening_job,
            "cron",
            minute="*",
            kwargs={"bot": bot, "db_path": config.db_path, "session": session, "tz": config.tz},
        )
        scheduler.add_job(
            run_weekly_job,
            "cron",
            minute="*",
            kwargs={"bot": bot, "db_path": config.db_path, "session": session, "tz": config.tz},
        )
        scheduler.start()
        logger.info("Scheduler started")

        try:
            await dp.start_polling(
                bot,
                db_path=config.db_path,
                session=session,
            )
        finally:
            scheduler.shutdown()
            logger.info("Scheduler stopped")


if __name__ == "__main__":
    asyncio.run(main())
