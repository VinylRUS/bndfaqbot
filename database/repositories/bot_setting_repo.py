from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.bot_setting import BotSetting


class BotSettingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, key: str) -> Optional[str]:
        result = await self.session.execute(
            select(BotSetting).where(BotSetting.key == key)
        )
        setting = result.scalar_one_or_none()
        return setting.value if setting else None

    async def set(self, key: str, value: str) -> BotSetting:
        result = await self.session.execute(
            select(BotSetting).where(BotSetting.key == key)
        )
        setting = result.scalar_one_or_none()
        if setting:
            setting.value = value
        else:
            setting = BotSetting(key=key, value=value)
            self.session.add(setting)
        await self.session.flush()
        return setting

    async def delete(self, key: str) -> bool:
        result = await self.session.execute(
            select(BotSetting).where(BotSetting.key == key)
        )
        setting = result.scalar_one_or_none()
        if setting:
            await self.session.delete(setting)
            await self.session.flush()
            return True
        return False
