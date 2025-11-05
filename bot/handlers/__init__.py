from __future__ import annotations

from aiogram import Router

from . import errors, search, start


def setup_router() -> Router:
    router = Router()
    router.include_router(start.router)
    router.include_router(search.router)
    router.include_router(errors.router)
    return router

