from __future__ import annotations

import json
import re
from typing import Dict, Iterable, List, Optional, Tuple
from urllib.parse import urljoin, urlsplit

from ..schemas import Product

ALLOWED_PRESENCE = {
    "в наличии",
    "готов к отправке",
    "готово к отправке",
    "готово до відправки",
    "в наявності",
}
CATALOG_PRESENCE_VALUE_MAP = {
    "presence_for_sure": "готово к отправке",
    "presence_sure": "готово к отправке",
    "presence_available": "в наличии",
    "presence_wait": "ожидается",
    "presence_preorder": "под заказ",
}
PRESENCE_CODE_MAP = {
    "avail": "в наличии",
    "available": "в наличии",
    "order": "под заказ",
    "wait": "ожидается",
    "in_stock": "в наличии",
}

APOLLO_RE = re.compile(r"window.ApolloCacheState = (\{.*?\});", re.S)
LISTING_KEY_PRIORITIES = (
    "CompanyListingQuery",
    "SearchProductsListingQuery",
    "CategoryListingQuery",
)


def normalize_price_value(price_text: str) -> str:
    if not price_text:
        return ""
    cleaned = price_text.strip().replace("\xa0", "").replace("\u202f", "").replace(" ", "")
    filtered = "".join(ch for ch in cleaned if ch.isdigit() or ch in ",.")
    if not filtered:
        return ""
    last_sep_pos = max(filtered.rfind("."), filtered.rfind(","))
    if last_sep_pos == -1:
        return filtered
    integer_part = "".join(ch for ch in filtered[:last_sep_pos] if ch.isdigit())
    fractional_part = "".join(ch for ch in filtered[last_sep_pos + 1 :] if ch.isdigit())
    if not integer_part:
        integer_part = "0"
    if fractional_part:
        return f"{integer_part},{fractional_part}"
    return integer_part


def extract_listing_entry(html: str) -> Dict:
    match = APOLLO_RE.search(html)
    if not match:
        raise ValueError("Не нашли window.ApolloCacheState в HTML")
    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError as error:
        raise ValueError(f"Не удалось разобрать Apollo кэш: {error}") from error

    fast_cache = data.get("_FAST_CACHE") or {}
    candidates: List[Tuple[str, Dict]] = []
    for key, value in fast_cache.items():
        if not isinstance(value, dict):
            continue
        result = value.get("result")
        if not isinstance(result, dict):
            continue
        listing = result.get("listing")
        if not isinstance(listing, dict):
            continue
        page = listing.get("page")
        if not isinstance(page, dict):
            continue
        products = page.get("products")
        if isinstance(products, list):
            candidates.append((key, value))

    if not candidates:
        available_keys = ", ".join(fast_cache.keys())
        raise ValueError(
            f"Не нашли листинг товаров в Apollo кэше. Доступные ключи: {available_keys}"
        )

    def priority(pair: Tuple[str, Dict]) -> Tuple[int, str]:
        key = pair[0]
        for idx, token in enumerate(LISTING_KEY_PRIORITIES):
            if token in key:
                return (idx, key)
        return (len(LISTING_KEY_PRIORITIES), key)

    _, entry = min(candidates, key=priority)
    return entry


def normalize_product(
    entry: Dict,
    base_root: str,
    company_lookup: Optional[Dict[str, str]] = None,
) -> Optional[Product]:
    product_data = entry.get("product") or {}

    presence_title = (entry.get("catalogPresence") or {}).get("title") or (
        product_data.get("catalogPresence") or {}
    ).get("title")
    if not presence_title:
        catalog_value = (entry.get("catalogPresence") or {}).get("value") or (
            product_data.get("catalogPresence") or {}
        ).get("value")
        presence_title = CATALOG_PRESENCE_VALUE_MAP.get(str(catalog_value).lower(), "")
    if not presence_title:
        presence_code = (entry.get("presence") or {}).get("presence") or (
            product_data.get("presence") or {}
        ).get("presence")
        presence_title = PRESENCE_CODE_MAP.get(str(presence_code).lower(), "")
    presence_title = (presence_title or "").strip()
    if presence_title.lower() not in ALLOWED_PRESENCE:
        return None

    price_text = product_data.get("discountedPrice") or product_data.get("price") or ""
    price_value = normalize_price_value(price_text)
    if not price_value:
        return None

    product_url = product_data.get("urlForProductCatalog") or product_data.get("url") or ""
    if not product_url:
        pid = product_data.get("id")
        slug = product_data.get("urlText") or product_data.get("slug")
        if pid and slug:
            product_url = f"/p{pid}-{slug}.html"
    if not product_url:
        return None

    def _extract_company_name(source: Optional[Dict]) -> str:
        if not isinstance(source, dict):
            return ""
        for key in ("name", "title", "companyName"):
            value = source.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    company_info = (
        entry.get("company")
        or product_data.get("company")
        or entry.get("companyInfo")
        or product_data.get("companyInfo")
        or {}
    )
    seller = _extract_company_name(company_info)
    if not seller:
        seller = _extract_company_name(entry) or _extract_company_name(product_data)
    if not seller:
        company_id = (
            entry.get("companyId")
            or (company_info.get("id") if isinstance(company_info, dict) else None)
            or product_data.get("companyId")
        )
        if company_id and company_lookup:
            seller = company_lookup.get(str(company_id), "")

    manufacturer = ((product_data.get("manufacturerInfo") or {}).get("name") or "").strip()
    product_abs_url = urljoin(base_root, product_url)

    return Product(
        url=product_abs_url,
        name=product_data.get("name") or "",
        price=price_value,
        presence=presence_title,
        seller=seller,
        manufacturer=manufacturer,
    )
