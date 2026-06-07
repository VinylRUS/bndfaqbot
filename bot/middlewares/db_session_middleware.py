from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery

from database.session import async_session_factory


class DbSessionMiddleware(BaseMiddleware):
    """Provides a DB session to every handler via data["db_session"].

    The bot instance is automatically injected by aiogram into data["bot"],
    so we don't need to handle it here. Handlers access it as data["bot"].
    """

    async def __call__(
        self,
        handler: Callable[[Message | CallbackQuery, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any],
    ) -> Any:
        async with async_session_factory() as session:
            data["db_session"] = session
            try:
                result = await handler(event, data)
                await session.commit()
                return result
            except Exception:
                await session.rollback()
                raise
