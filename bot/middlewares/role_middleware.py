from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery

from database.models.role import RoleEnum
from database.repositories.user_repo import UserRepository
from database.repositories.role_repo import RoleRepository


class RoleMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message | CallbackQuery, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any],
    ) -> Any:
        session = data.get("db_session")
        if not session:
            return await handler(event, data)

        from_user = getattr(event, "from_user", None)
        if not from_user:
            return await handler(event, data)

        user_repo = UserRepository(session)
        role_repo = RoleRepository(session)

        db_user = await user_repo.get_by_telegram_id(from_user.id)

        # Auto-register user if they don't exist yet
        if not db_user:
            default_role = await role_repo.get_or_create(RoleEnum.USER)
            db_user = await user_repo.create(
                telegram_id=from_user.id,
                role_id=default_role.id,
                username=from_user.username,
                first_name=from_user.first_name,
                last_name=from_user.last_name,
            )
            await session.flush()

        if db_user.role:
            role_name = db_user.role.name
            if hasattr(role_name, "value"):
                data["user_role"] = RoleEnum(role_name.value)
            else:
                data["user_role"] = RoleEnum(str(role_name))
        else:
            data["user_role"] = RoleEnum.USER

        data["db_user"] = db_user

        return await handler(event, data)
