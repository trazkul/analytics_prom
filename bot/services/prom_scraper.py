from __future__ import annotations

from typing import List
from urllib.parse import urlsplit

import httpx

from ..schemas import Product
from .prom_utils import extract_listing_entry, normalize_product

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru,uk;q=0.8,en;q=0.6",
}


class PromScraper:
    def __init__(self, client: httpx.AsyncClient, base_url: str) -> None:
        self._client = client
        self._base_url = base_url

    async def fetch_first_page(self, query: str) -> List[Product]:
        params = {"search_term": query}
        response = await self._client.get(
            self._base_url,
            params=params,
            headers=DEFAULT_HEADERS,
            timeout=30.0,
        )
        response.raise_for_status()

        entry = extract_listing_entry(response.text)
        listing = entry["result"]["listing"]
        page = listing["page"]
        raw_products = page.get("products") or []

        company_lookup = {}
        def register_company(comp: dict) -> None:
            if not isinstance(comp, dict):
                return
            identifier = comp.get("id") or comp.get("companyId")
            if not identifier:
                return
            name = (comp.get("name") or comp.get("title") or "").strip()
            if name:
                company_lookup[str(identifier)] = name

        def register_container(container) -> None:
            if isinstance(container, dict):
                for key, value in container.items():
                    if isinstance(value, dict) and (value.get("id") is None):
                        value = {**value, "id": value.get("id") or key}
                    register_company(value)
            elif isinstance(container, list):
                for comp in container:
                    register_company(comp)

        register_container(page.get("companies"))
        register_container(page.get("companiesMap"))
        register_container(listing.get("companies"))
        register_container(listing.get("companiesMap"))

        parts = urlsplit(str(response.url))
        base_root = f"{parts.scheme}://{parts.netloc}"

        items: List[Product] = []
        for raw in raw_products:
            product = normalize_product(raw, base_root, company_lookup)
            if product:
                items.append(product)
        return items
