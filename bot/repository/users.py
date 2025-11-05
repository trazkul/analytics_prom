from __future__ import annotations

from aiogram.types import User as TelegramUser

from . import Database


async def ensure_user(db: Database, user: TelegramUser) -> None:
    query = """
        INSERT INTO users (id, username)
        VALUES ($1, $2)
        ON CONFLICT (id) DO UPDATE
            SET username = EXCLUDED.username
    """
    await db.execute(query, user.id, user.username)
