from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from ..config import Config
from ..repository import Database
from ..repository.users import ensure_user

router = Router()

HELP_TEXT = (
    "Как пользоваться ботом:\n"
    "• Отправьте одно или несколько поисковых выражений через запятую или точку.\n"
    "• Бот соберёт товары с первой страницы Prom.ua и пришлёт Excel.\n"
    "• Лимит — {limit} запросов в сутки. Повторные запросы тоже учитываются."
)


@router.message(CommandStart())
async def handle_start(message: Message, config: Config, db: Database) -> None:
    await ensure_user(db, message.from_user)
    channels = ", ".join(config.required_channels) if config.required_channels else "—"
    await message.answer(
        "Привет, отправь мне поисковые запросы через запятую или точку, и я пришлю товары с первой страницы Prom.ua.\n"
        "Пример: Чехол для Iphone 17 pro, Чехол Samsung Galaxy S25.\n"
        f"Ограничение: {config.daily_query_limit} запросов в сутки.\n"
        f"Обязательные каналы: {channels}"
    )


@router.message(Command("help"))
async def handle_help(message: Message, config: Config) -> None:
    await message.answer(HELP_TEXT.format(limit=config.daily_query_limit))


@router.message(Command("services"))
async def handle_services(message: Message, config: Config) -> None:
    parts = [
        "Услуги:",
        f"• Индивидуальный парсер — {config.order_parser_url or 'напишите разработчику'}",
        f"• Продвижение товаров в топ — {config.boost_products_url or 'свяжитесь с разработчиком'}",
    ]
    await message.answer("\n".join(parts))
