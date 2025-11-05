import argparse
import csv
import json
import math
import random
import re
import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple, Union
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import requests

# Парсер по ссылке на категорию
# Можно указать строку с одним URL или перечисление нескольких URL.
DEFAULT_START_URLS: Union[str, Iterable[str]] = (
    "https://prom.ua/c3825812-riverwood-internet-magazin.html"
)
OUTPUT_CSV = "Столовая_посуда.csv"
DEFAULT_MAX_PAGES = 0
DEFAULT_LISTING_DELAY_RANGE = (0.5, 1.5)
DEFAULT_PRODUCT_DELAY_RANGE = (0.1, 0.3)
RETRY_ATTEMPTS = 3
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


def build_page_url(base_url: str, page_number: int) -> str:
    if page_number <= 1:
        return base_url

    parts = urlsplit(base_url)
    query_items = parse_qsl(parts.query, keep_blank_values=True)
    if query_items or "?" in base_url:
        params = dict(query_items)
        params["page"] = str(page_number)
        new_query = urlencode(params, doseq=True)
        return urlunsplit(
            (parts.scheme, parts.netloc, parts.path, new_query, parts.fragment)
        )

    path = parts.path
    if path.endswith(".html"):
        base_path = path[:-5]
        new_path = f"{base_path};{page_number}.html"
    else:
        new_path = f"{path};{page_number}"
    return urlunsplit(
        (parts.scheme, parts.netloc, new_path, parts.query, parts.fragment)
    )


def sleep_between_requests(delay_range: Optional[Tuple[float, float]] = None) -> None:
    if delay_range is None:
        delay_range = DEFAULT_LISTING_DELAY_RANGE
    if not delay_range:
        return
    min_delay, max_delay = delay_range
    min_delay = max(0.0, float(min_delay))
    max_delay = max(min_delay, float(max_delay))
    if max_delay <= 0:
        return
    time.sleep(random.uniform(min_delay, max_delay))


def normalize_price_value(price_text: str) -> str:
    if not price_text:
        return ""

    cleaned = (
        price_text.strip().replace("\xa0", "").replace("\u202f", "").replace(" ", "")
    )
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


def normalize_product(raw: Dict) -> Optional[Dict[str, str]]:
    product = raw.get("product") or {}
    presence_title = (raw.get("catalogPresence") or {}).get("title") or (
        product.get("catalogPresence") or {}
    ).get("title")
    if not presence_title:
        catalog_value = (raw.get("catalogPresence") or {}).get("value") or (
            product.get("catalogPresence") or {}
        ).get("value")
        presence_title = CATALOG_PRESENCE_VALUE_MAP.get(str(catalog_value).lower(), "")
    if not presence_title:
        presence_code = (raw.get("presence") or {}).get("presence") or (
            product.get("presence") or {}
        ).get("presence")
        presence_title = PRESENCE_CODE_MAP.get(str(presence_code).lower(), "")
    presence_title = (presence_title or "").strip()
    if presence_title.lower() not in ALLOWED_PRESENCE:
        return None

    price_text = product.get("discountedPrice") or product.get("price") or ""
    price_value = normalize_price_value(price_text)
    if not price_value:
        return None

    product_url = product.get("urlForProductCatalog") or product.get("url") or ""
    if not product_url:
        pid = product.get("id")
        slug = product.get("urlText") or product.get("slug")
        if pid and slug:
            product_url = f"/p{pid}-{slug}.html"
    if not product_url:
        return None

    manufacturer = ((product.get("manufacturerInfo") or {}).get("name") or "").strip()

    return {
        "url": product_url,
        "name": product.get("name") or "",
        "bought": str(product.get("ordersCount") or ""),
        "price": price_value,
        "presence": presence_title,
        "manufacturer": manufacturer,
    }


def extract_manufacturer_from_product_page(html: str) -> str:
    try:
        match = APOLLO_RE.search(html)
        if not match:
            return ""
        data = json.loads(match.group(1))
    except (json.JSONDecodeError, ValueError):
        return ""

    fast_cache = data.get("_FAST_CACHE") or {}
    for value in fast_cache.values():
        if not isinstance(value, dict):
            continue
        product = (value.get("result") or {}).get("product")
        if not isinstance(product, dict):
            continue
        manufacturer = (
            (product.get("manufacturerInfo") or {}).get("name") or ""
        ).strip()
        if manufacturer:
            return manufacturer
    return ""


def fill_missing_manufacturers(
    session: requests.Session, products: List[Dict[str, str]], base_url: str
) -> None:
    if not products:
        return

    parts = urlsplit(base_url)
    base = f"{parts.scheme}://{parts.netloc}"
    cache: Dict[str, str] = {}

    for item in products:
        if item.get("manufacturer"):
            continue
        product_url = item.get("url")
        if not product_url:
            continue
        absolute_url = urljoin(base, product_url)
        if absolute_url in cache:
            item["manufacturer"] = cache[absolute_url]
            continue

        try:
            sleep_between_requests(DEFAULT_PRODUCT_DELAY_RANGE)
            resp = session.get(absolute_url)
            resp.raise_for_status()
        except requests.RequestException as error:
            print(f"Не удалось получить производителя для {product_url}: {error}")
            cache[absolute_url] = ""
            continue

        manufacturer = extract_manufacturer_from_product_page(resp.text) or ""
        cache[absolute_url] = manufacturer
        item["manufacturer"] = manufacturer


def parse_products(html: str) -> Dict[str, Iterable[Dict[str, str]]]:
    entry = extract_listing_entry(html)
    listing = entry["result"]["listing"]
    page = listing["page"]
    products = page.get("products") or []

    variables = entry.get("variables") or {}
    limit = variables.get("limit") or listing.get("limit") or len(products) or 1

    total = page.get("total")
    if isinstance(total, dict):
        total = total.get("count") or total.get("value")
    total = total or 0

    return {
        "products": products,
        "limit": limit,
        "total": total,
    }


def gather_all_products(
    session: requests.Session, start_url: str, max_pages: Optional[int] = None
) -> List[Dict[str, str]]:
    parsed: Optional[Dict[str, Iterable[Dict[str, str]]]] = None
    last_error: Optional[ValueError] = None

    for attempt in range(RETRY_ATTEMPTS):
        sleep_between_requests()
        first_resp = session.get(start_url)
        first_resp.raise_for_status()
        first_html = first_resp.text
        try:
            parsed = parse_products(first_html)
            break
        except ValueError as error:
            last_error = error
            if attempt < RETRY_ATTEMPTS - 1:
                print(f"Повтор запроса {start_url}: {error}")
                continue
            raise error

    if parsed is None:
        raise last_error or ValueError("Не удалось разобрать первую страницу")

    limit = parsed["limit"]
    total = parsed["total"]
    pages = 1
    if total and limit:
        pages = max(1, math.ceil(total / limit))

    if max_pages:
        pages = min(pages, max_pages)

    parts = urlsplit(start_url)
    base_root = f"{parts.scheme}://{parts.netloc}"

    seen = set()
    collected: List[Dict[str, str]] = []

    def consume(raw_products: Iterable[Dict]):
        for raw in raw_products:
            item = normalize_product(raw)
            if not item:
                continue
            url = urljoin(base_root, item["url"])
            if not url or url in seen:
                continue
            seen.add(url)
            item["url"] = url
            collected.append(item)

    consume(parsed["products"])

    for page_number in range(2, pages + 1):
        page_url = build_page_url(start_url, page_number)
        stop_pagination = False
        skip_page = False
        parsed_page: Optional[Dict[str, Iterable[Dict[str, str]]]] = None

        for attempt in range(RETRY_ATTEMPTS):
            sleep_between_requests()
            resp = session.get(page_url)

            if resp.status_code in (404, 410):
                stop_pagination = True
                break
            if resp.status_code >= 500:
                print(f"Пропускаем страницу {page_number}: {resp.status_code}")
                skip_page = True
                break

            resp.raise_for_status()
            try:
                parsed_page = parse_products(resp.text)
                break
            except ValueError as error:
                if attempt < RETRY_ATTEMPTS - 1:
                    print(
                        f"Повтор запроса страницы {page_number} для {start_url}: {error}"
                    )
                    continue
                print(f"Пропускаем страницу {page_number}: {error}")
                skip_page = True

        if stop_pagination:
            break
        if skip_page or not parsed_page:
            continue
        if not parsed_page["products"]:
            break
        consume(parsed_page["products"])

    return collected


def write_csv(rows: Iterable[Dict[str, str]], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            ["idx", "url", "name", "bought", "price", "presence", "manufacturer"]
        )
        for idx, row in enumerate(rows, start=1):
            writer.writerow(
                [
                    idx,
                    row.get("url", ""),
                    row.get("name", ""),
                    row.get("bought", ""),
                    row.get("price", ""),
                    row.get("presence", ""),
                    row.get("manufacturer", ""),
                ]
            )


def read_start_urls(path: Optional[Path]) -> List[str]:
    if not path:
        return []
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def normalize_start_urls(raw: Union[str, Iterable[str]]) -> List[str]:
    if not raw:
        return []
    if isinstance(raw, str):
        url = raw.strip()
        return [url] if url else []
    result: List[str] = []
    for url in raw:
        if not url:
            continue
        cleaned = str(url).strip()
        if cleaned:
            result.append(cleaned)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Парсинг товаров Prom.ua по поисковым или категорийным ссылкам"
    )
    parser.add_argument(
        "--url",
        dest="urls",
        action="append",
        metavar="START_URL",
        help="URL страницы поиска или категории Prom.ua (можно указывать несколько раз)",
    )
    parser.add_argument(
        "--urls-file",
        type=Path,
        help="Путь к файлу со списком URL (по одному на строку)",
    )
    parser.add_argument("--output", default=OUTPUT_CSV, help="Файл для сохранения CSV")
    parser.add_argument(
        "--max-pages",
        type=int,
        default=DEFAULT_MAX_PAGES,
        help="Максимум страниц для обхода (по умолчанию 0 — без ограничения). Укажите положительное число, чтобы ограничить.",
    )
    args = parser.parse_args()

    urls = normalize_start_urls(args.urls or [])
    urls.extend(read_start_urls(args.urls_file))
    if not urls:
        urls = normalize_start_urls(DEFAULT_START_URLS)

    if not urls:
        print("Не заданы стартовые URL. Передайте их через --url или --urls-file.")
        return

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ru,uk;q=0.8,en;q=0.6",
        }
    )

    all_products: List[Dict[str, str]] = []
    global_seen = set()

    max_pages = args.max_pages if args.max_pages and args.max_pages > 0 else None

    for url in urls:
        try:
            products = gather_all_products(session, url, max_pages=max_pages)
        except requests.RequestException as error:
            print(f"Не удалось собрать товары для {url}: {error}")
            continue
        except ValueError as error:
            print(f"Ошибка при обработке {url}: {error}")
            continue

        fill_missing_manufacturers(session, products, url)

        for item in products:
            product_url = item.get("url", "")
            if product_url and product_url in global_seen:
                continue
            if product_url:
                global_seen.add(product_url)
            all_products.append(item)

    write_csv(all_products, Path(args.output))
    print(f"Сохранено {len(all_products)} товаров в {args.output}")


if __name__ == "__main__":
    main()
