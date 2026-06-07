from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from database.models.role import RoleEnum
from database.models.user import User
from database.repositories.role_repo import RoleRepository


class RoleMiddleware(BaseMiddleware):
    """Loads the current user + role from DB and injects into handler data.

    Data keys added:
      - "db_user"   — the User ORM object (with .role loaded)
      - "user_role" — RoleEnum value (ADMIN / OPERATOR / USER)
    """

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

        # Load ONLY User + Role (no tickets, ratings, audit_logs cascade)
        stmt = (
            select(User)
            .where(User.telegram_id == from_user.id)
            .options(selectinload(User.role))
        )
        result = await session.execute(stmt)
        db_user = result.scalar_one_or_none()

        # Auto-register user if they don't exist yet
        if not db_user:
            role_repo = RoleRepository(session)
            default_role = await role_repo.get_or_create(RoleEnum.USER)
            db_user = User(
                telegram_id=from_user.id,
                role_id=default_role.id,
                username=from_user.username,
                first_name=from_user.first_name,
                last_name=from_user.last_name,
            )
            session.add(db_user)
            await session.flush()
            # Refresh to load role relationship
            await session.refresh(db_user, ["role"])

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
