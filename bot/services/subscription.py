from __future__ import annotations

from typing import Iterable, List, Sequence

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramNotFound
from aiogram.types import ChatMember


async def check_subscription(bot: Bot, user_id: int, channels: Sequence[str]) -> List[str]:
    missing: List[str] = []
    for channel in channels:
        try:
            member: ChatMember = await bot.get_chat_member(channel, user_id)
        except (TelegramForbiddenError, TelegramNotFound, TelegramBadRequest):
            missing.append(channel)
            continue
        if member.status in ("left", "kicked"):
            missing.append(channel)
    return missing
