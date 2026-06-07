from __future__ import annotations

from typing import Any, Dict, Union

from aiogram.types import Message, CallbackQuery
from aiogram.filters import BaseFilter

from database.models.role import RoleEnum


class RoleFilter(BaseFilter):
    """Filter that checks user role from middleware-injected data["user_role"]."""

    def __init__(self, roles: Union[RoleEnum, list[RoleEnum]]) -> None:
        if isinstance(roles, RoleEnum):
            self.roles = [roles]
        else:
            self.roles = roles

    async def __call__(
        self,
        event: Union[Message, CallbackQuery],
        data: Dict[str, Any],
    ) -> bool:
        user_role: RoleEnum | None = data.get("user_role")
        if user_role is None:
            return False
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
