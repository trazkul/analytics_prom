from __future__ import annotations

from io import BytesIO
from typing import Iterable, List

from openpyxl import Workbook

from ..schemas import SearchResult


def render_text(results: Iterable[SearchResult]) -> str:
    lines: List[str] = []
    for result in results:
        lines.append(f"Поиск: {result.query}")
        if not result.products:
            lines.append("  Ничего не найдено или нет доступных товаров.")
            continue
        for idx, product in enumerate(result.products, start=1):
            lines.append(
                f"{idx}. {product.name} — {product.price} — {product.presence} — {product.seller} — {product.manufacturer}\n   {product.url}"
            )
    return "\n".join(lines)


def render_excel(results: Iterable[SearchResult]) -> BytesIO:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Prom Search"
    sheet.append(
        [
            "Запрос",
            "№ позиции",
            "Название позиции",
            "Цена",
            "Статус",
            "Продавець",
            "Бренд",
            "Ссылка на товар",
        ]
    )
    for result in results:
        for idx, product in enumerate(result.products, start=1):
            sheet.append(
                [
                    result.query,
                    idx,
                    product.name,
                    product.price,
                    product.presence,
                    product.seller,
                    product.manufacturer,
                    product.url,
                ]
            )
    buffer = BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    return buffer
