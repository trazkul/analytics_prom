from __future__ import annotations

from dataclasses import dataclass

from ..repository import Database
from ..repository import search_logs


@dataclass
class LimitStatus:
    allowed: bool
    remaining: int
    used: int


async def check_limit(db: Database, user_id: int, capacity: int, requested: int) -> LimitStatus:
    used = await search_logs.count_requests_today(db, user_id)
    remaining = max(capacity - used, 0)
    allowed = requested <= remaining
    return LimitStatus(allowed=allowed, remaining=remaining, used=used)


async def register_queries(db: Database, user_id: int, queries: list[str]) -> None:
    await search_logs.add_queries(db, user_id, queries)

