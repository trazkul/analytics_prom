from __future__ import annotations

from typing import Iterable, Sequence

from . import Database


async def count_requests_today(db: Database, user_id: int) -> int:
    query = """
        SELECT COUNT(*)
        FROM search_logs
        WHERE user_id = $1
          AND created_at >= date_trunc('day', timezone('UTC', now()))
    """
    value = await db.fetchval(query, user_id)
    return int(value or 0)


async def add_queries(db: Database, user_id: int, queries: Sequence[str]) -> None:
    if not queries:
        return
    query = """
        INSERT INTO search_logs (user_id, query)
        SELECT $1, q::text
        FROM unnest($2::text[]) AS q
    """
    await db.execute(query, user_id, list(queries))

