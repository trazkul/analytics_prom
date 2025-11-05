from __future__ import annotations

from typing import Any, Iterable, Optional

import asyncpg


class Database:
    """Thin asyncpg wrapper to keep SQL close to services."""

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._pool: Optional[asyncpg.Pool] = None

    async def connect(self) -> None:
        if self._pool is None:
            self._pool = await asyncpg.create_pool(dsn=self._dsn, min_size=1, max_size=5)

    async def disconnect(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    async def fetch(self, query: str, *args: Any) -> Iterable[asyncpg.Record]:
        assert self._pool is not None, "Database pool is not initialized"
        async with self._pool.acquire() as connection:
            return await connection.fetch(query, *args)

    async def fetchrow(self, query: str, *args: Any) -> Optional[asyncpg.Record]:
        assert self._pool is not None, "Database pool is not initialized"
        async with self._pool.acquire() as connection:
            return await connection.fetchrow(query, *args)

    async def fetchval(self, query: str, *args: Any) -> Any:
        assert self._pool is not None, "Database pool is not initialized"
        async with self._pool.acquire() as connection:
            return await connection.fetchval(query, *args)

    async def execute(self, query: str, *args: Any) -> str:
        assert self._pool is not None, "Database pool is not initialized"
        async with self._pool.acquire() as connection:
            return await connection.execute(query, *args)

