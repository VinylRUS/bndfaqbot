from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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

    async def get_all(self) -> list[User]:
        result = await self.session.execute(select(User))
        return list(result.scalars().all())

    async def get_by_role(self, role_name: RoleEnum) -> list[User]:
        from database.models.role import Role
        result = await self.session.execute(
            select(User).join(Role).where(Role.name == role_name)
        )
        return list(result.scalars().all())

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
        from sqlalchemy import func
        result = await self.session.execute(select(func.count(User.id)))
        return result.scalar_one()
