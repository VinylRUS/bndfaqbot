from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from database.models.role import RoleEnum
from database.models.user import User
from database.repositories.user_repo import UserRepository
from database.repositories.role_repo import RoleRepository
from database.repositories.audit_log_repo import AuditLogRepository


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.user_repo = UserRepository(session)
        self.role_repo = RoleRepository(session)
        self.audit_repo = AuditLogRepository(session)

    async def get_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        return await self.user_repo.get_by_telegram_id(telegram_id)

    async def get_by_id(self, user_id: int) -> Optional[User]:
        return await self.user_repo.get_by_id(user_id)

    async def register_or_update(
        self,
        telegram_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
    ) -> User:
        user = await self.user_repo.get_by_telegram_id(telegram_id)
        if user:
            if username is not None:
                user.username = username
            if first_name is not None:
                user.first_name = first_name
            if last_name is not None:
                user.last_name = last_name
            await self.session.flush()
            return user

        default_role = await self.role_repo.get_or_create(RoleEnum.USER)
        user = await self.user_repo.create(
            telegram_id=telegram_id,
            role_id=default_role.id,
            username=username,
            first_name=first_name,
            last_name=last_name,
        )
        return user

    async def update_phone(self, telegram_id: int, phone: str) -> Optional[User]:
        return await self.user_repo.update_phone(telegram_id, phone)

    async def change_role(
        self,
        admin_telegram_id: int,
        target_user_id: int,
        new_role: RoleEnum,
    ) -> Optional[User]:
        role = await self.role_repo.get_or_create(new_role)
        user = await self.user_repo.update_role(target_user_id, role.id)
        if user:
            await self.audit_repo.create(
                user_id=admin_telegram_id,
                role="admin",
                action="change_role",
                object_type="user",
                object_id=target_user_id,
                details=f"Changed role to {new_role.value}",
            )
        return user

    async def get_all_users(self) -> list[User]:
        return await self.user_repo.get_all()

    async def get_operators(self) -> list[User]:
        return await self.user_repo.get_by_role(RoleEnum.OPERATOR)

    async def get_admins(self) -> list[User]:
        return await self.user_repo.get_by_role(RoleEnum.ADMIN)

    async def count_users(self) -> int:
        return await self.user_repo.count()

    async def ensure_admin(self, telegram_id: int) -> User:
        user = await self.user_repo.get_by_telegram_id(telegram_id)
        if user:
            admin_role = await self.role_repo.get_or_create(RoleEnum.ADMIN)
            if user.role_id != admin_role.id:
                user.role_id = admin_role.id
                await self.session.flush()
            return user

        admin_role = await self.role_repo.get_or_create(RoleEnum.ADMIN)
        user = await self.user_repo.create(
            telegram_id=telegram_id,
            role_id=admin_role.id,
        )
        return user

    def get_role_name(self, user: User) -> str:
        if user.role:
            return user.role.name.value if hasattr(user.role.name, "value") else str(user.role.name)
        return "user"
