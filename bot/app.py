from __future__ import annotations

import asyncio
import logging

import httpx
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand

from .config import Config, load_config
from .handlers import setup_router
from .repository import Database
from .services.prom_scraper import PromScraper


async def _create_http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(follow_redirects=True)


async def _setup_bot_commands(bot: Bot) -> None:
    commands = [
        BotCommand(command="start", description="Начать работу"),
        BotCommand(command="help", description="Правила использования"),
        BotCommand(command="services", description="Услуги и продвижение"),
    ]
    await bot.set_my_commands(commands)


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    config: Config = load_config()
    bot = Bot(token=config.bot_token)
    dp = Dispatcher()
    dp.include_router(setup_router())

    db = Database(config.postgres_dsn)
    await db.connect()

    http_client = await _create_http_client()
    scraper = PromScraper(http_client, base_url=config.prom_base_url)

    dp["config"] = config
    dp["db"] = db
    dp["scraper"] = scraper

    try:
        await _setup_bot_commands(bot)
        await dp.start_polling(bot)
    finally:
        await http_client.aclose()
        await db.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
