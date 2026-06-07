from __future__ import annotations

from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.models.user import User
from database.models.role import RoleEnum


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, user_id: int) -> Optional[User]:
        result = await self.session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        result = await self.session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()

    async def get_by_telegram_id_with_role(self, telegram_id: int) -> Optional[User]:
        """Load User with Role only — lightweight, for middleware."""
        stmt = (
            select(User)
            .where(User.telegram_id == telegram_id)
            .options(selectinload(User.role))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all(self, limit: int = 100, offset: int = 0) -> list[User]:
        """DB-level pagination — never load all users at once."""
        stmt = (
            select(User)
            .options(selectinload(User.role))
            .order_by(User.id)
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_all(self) -> int:
        result = await self.session.execute(select(func.count(User.id)))
        return result.scalar_one()

    async def get_by_role(self, role_name: RoleEnum, limit: int = 100) -> list[User]:
        from database.models.role import Role
        stmt = (
            select(User)
            .join(Role)
            .where(Role.name == role_name)
            .options(selectinload(User.role))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_by_role(self, role_name: RoleEnum) -> int:
        """Count users by role without loading any User objects."""
        from database.models.role import Role
        result = await self.session.execute(
            select(func.count(User.id)).join(Role).where(Role.name == role_name)
        )
        return result.scalar_one()

    async def create(
        self,
        telegram_id: int,
        role_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        phone: Optional[str] = None,
    ) -> User:
        user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            role_id=role_id,
        )
        self.session.add(user)
        await self.session.flush()
        return user

    async def update_role(self, user_id: int, role_id: int) -> Optional[User]:
        user = await self.get_by_id(user_id)
        if user:
            user.role_id = role_id
            await self.session.flush()
        return user

    async def update_phone(self, telegram_id: int, phone: str) -> Optional[User]:
        user = await self.get_by_telegram_id(telegram_id)
        if user:
            user.phone = phone
            await self.session.flush()
        return user

    async def count(self) -> int:
        result = await self.session.execute(select(func.count(User.id)))
        return result.scalar_one()
