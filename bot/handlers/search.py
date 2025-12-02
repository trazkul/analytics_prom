from __future__ import annotations

from datetime import datetime, timedelta
from typing import List

import httpx
from aiogram import Router
from aiogram.types import BufferedInputFile, Message

from ..config import Config
from ..repository import Database
from ..repository.search_logs import add_queries
from ..repository.users import ensure_user
from ..schemas import Product, SearchResult
from ..services.prom_scraper import PromScraper
from ..services.query_parser import split_queries
from ..services.rate_limit import check_limit
from ..services.subscription import check_subscription
from ..utils.text import render_excel

router = Router()


@router.message()
async def handle_search(
    message: Message,
    config: Config,
    db: Database,
    scraper: PromScraper,
) -> None:
    if not message.text:
        return

    queries = split_queries(message.text)
    if not queries:
        await message.answer("Введите хотя бы один поисковый запрос.")
        return

    await ensure_user(db, message.from_user)

    missing_channels = await check_subscription(
        message.bot, message.from_user.id, config.required_channels
    )
    if missing_channels:
        channels_list = ", ".join(missing_channels)
        await message.answer(
            "Подпишитесь на обязательные каналы, чтобы пользоваться ботом:\n"
            f"{channels_list}"
        )
        return

    limit_status = await check_limit(
        db, message.from_user.id, config.daily_query_limit, len(queries)
    )
    if limit_status.remaining <= 0:
        contact = config.order_parser_url or "@mashulia_prom"
        await message.answer(
            "Дневной лимит запросов исчерпан. Оформите безлимит за $20/30 дней — "
            f"пишите в Telegram: {contact}. Иначе попробуйте снова завтра."
        )
        return

    allowed_queries = queries[: limit_status.remaining]
    skipped = queries[limit_status.remaining :]

    now = datetime.utcnow()
    results: List[SearchResult] = []

    for query in allowed_queries:
        try:
            products = await scraper.fetch_first_page(query)
        except (httpx.HTTPError, ValueError) as error:
            await message.answer(f"Не удалось обработать запрос '{query}': {error}")
            results.append(SearchResult(query=query, products=[], fetched_at=now))
            continue
        results.append(SearchResult(query=query, products=products, fetched_at=now))

    processed_count = len(results)
    remaining_after = max(limit_status.remaining - processed_count, 0)
    used_after = limit_status.used + processed_count

    if results:
        await add_queries(db, message.from_user.id, [item.query for item in results])
        excel_buffer = render_excel(results)
        timestamp = now.strftime("%Y_%m_%d")
        file = BufferedInputFile(
            excel_buffer.getvalue(),
            filename=f"prom_{timestamp}.xlsx",
        )
        caption = (
            f"Результаты поиска Prom.ua\n"
            f"Использовано запросов: {used_after}/{config.daily_query_limit}"
        )
        await message.answer_document(file, caption=caption)
    else:
        await message.answer("Ничего не удалось собрать. Попробуйте позже.")

    if skipped:
        skipped_text = ", ".join(skipped)
        await message.answer(
            f"Лимит на сегодня почти исчерпан. Эти запросы не обработаны: {skipped_text}"
        )
