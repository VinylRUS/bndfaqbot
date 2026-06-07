from __future__ import annotations

from typing import Union

from aiogram.types import Message, CallbackQuery
from aiogram.filters import BaseFilter

from app.database.models.role import RoleEnum


class RoleFilter(BaseFilter):
    def __init__(self, roles: Union[RoleEnum, list[RoleEnum]]) -> None:
        if isinstance(roles, RoleEnum):
            self.roles = [roles]
        else:
            self.roles = roles

    async def __call__(self, event: Union[Message, CallbackQuery]) -> bool:
        user = getattr(event, "user", None)
        if user is None and hasattr(event, "from_user"):
            user_data = event.from_user
        else:
            user_data = user

        if not hasattr(event, "from_user") and not hasattr(event, "user"):
            return False

        from_user = getattr(event, "from_user", None)
        if from_user is None:
            return False

        db_user = getattr(event, "db_user", None)
        if db_user is None:
            return False

        user_role = db_user.role.name if db_user.role else RoleEnum.USER
        if hasattr(user_role, "value"):
            user_role = RoleEnum(user_role.value)
        return user_role in self.roles


class IsAdmin(RoleFilter):
    def __init__(self) -> None:
        super().__init__([RoleEnum.ADMIN])


class IsOperator(RoleFilter):
    def __init__(self) -> None:
        super().__init__([RoleEnum.OPERATOR, RoleEnum.ADMIN])


class IsUser(RoleFilter):
    def __init__(self) -> None:
        super().__init__([RoleEnum.USER, RoleEnum.OPERATOR, RoleEnum.ADMIN])
