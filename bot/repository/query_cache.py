from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

from . import Database


async def get_cached(
    db: Database, user_id: int, query: str, now: datetime
) -> Optional[dict]:
    sql = """
        SELECT payload
        FROM query_cache
        WHERE user_id = $1
          AND query = $2
          AND expires_at > $3
        ORDER BY created_at DESC
        LIMIT 1
    """
    record = await db.fetchrow(sql, user_id, query, now)
    if record is None:
        return None
    payload = record["payload"]
    if isinstance(payload, str):
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            return None
    return payload


async def store_cache(
    db: Database,
    user_id: int,
    query: str,
    payload: dict[str, Any],
    expires_at: datetime,
) -> None:
    sql = """
        INSERT INTO query_cache (user_id, query, payload, expires_at)
        VALUES ($1, $2, $3, $4)
    """
    payload_json = json.dumps(payload, ensure_ascii=False)
    await db.execute(sql, user_id, query, payload_json, expires_at)
