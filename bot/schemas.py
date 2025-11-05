from __future__ import annotations

from datetime import datetime
from typing import List, Sequence

from pydantic import BaseModel, Field, ConfigDict


class Product(BaseModel):
    model_config = ConfigDict(extra="ignore")

    url: str
    name: str
    price: str = ""
    presence: str = ""
    seller: str = ""
    manufacturer: str = ""


class SearchRequest(BaseModel):
    user_id: int
    queries: Sequence[str]


class SearchResult(BaseModel):
    query: str
    products: List[Product] = Field(default_factory=list)
    fetched_at: datetime = Field(default_factory=datetime.utcnow)
