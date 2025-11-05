from __future__ import annotations

from functools import lru_cache
from typing import List, Sequence

from pydantic import Field, PrivateAttr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    bot_token: str = Field(..., env="BOT_TOKEN")
    postgres_dsn: str = Field(..., env="POSTGRES_DSN")
    required_channels_raw: str | None = Field(default=None, alias="REQUIRED_CHANNELS")
    daily_query_limit: int = Field(default=10, ge=1, env="DAILY_QUERY_LIMIT")
    cache_ttl_seconds: int = Field(default=3600, ge=0, env="CACHE_TTL_SECONDS")
    prom_base_url: str = Field(
        default="https://prom.ua/search",
        env="PROM_SEARCH_URL",
    )
    developer_contact_url: str = Field(default="", env="DEVELOPER_CONTACT_URL")
    order_parser_url: str = Field(default="", env="ORDER_PARSER_URL")
    boost_products_url: str = Field(default="", env="BOOST_PRODUCTS_URL")

    _channels: List[str] = PrivateAttr(default_factory=list)

    def __init__(self, **data):
        super().__init__(**data)
        raw = self.required_channels_raw or ""
        if raw:
            self._channels = [item.strip() for item in raw.split(",") if item.strip()]

    @property
    def required_channels(self) -> List[str]:
        return list(self._channels)


@lru_cache(maxsize=1)
def load_config() -> Config:
    return Config()
