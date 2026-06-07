from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.redis import RedisStorage

from app.config.settings import get_settings
from app.database.session import create_tables
from app.database.repositories.category_repo import CategoryRepository
from app.database.repositories.role_repo import RoleRepository
from app.database.session import async_session_factory
from app.services.user_service import UserService
from app.bot.middlewares.db_session_middleware import DbSessionMiddleware
from app.bot.middlewares.role_middleware import RoleMiddleware
from app.bot.routers.user_router import user_router
from app.bot.routers.operator_router import operator_router
from app.bot.routers.admin_router import admin_router


async def seed_database() -> None:
    async with async_session_factory() as session:
        role_repo = RoleRepository(session)
        for role_name in ["admin", "operator", "user"]:
            from app.database.models.role import RoleEnum
            await role_repo.get_or_create(RoleEnum(role_name))

        cat_repo = CategoryRepository(session)
        await cat_repo.seed_defaults()

        settings = get_settings()
        user_service = UserService(session)
        for admin_id in settings.admin_ids:
            await user_service.ensure_admin(admin_id)

        await session.commit()


async def main() -> None:
    settings = get_settings()

    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stdout,
    )
    logger = logging.getLogger(__name__)

    await create_tables()
    await seed_database()
    logger.info("Database tables created and seeded.")

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode="HTML"),
    )

    redis_url = settings.redis_url
    storage = RedisStorage.from_url(redis_url)

    dp = Dispatcher(storage=storage)

    dp.message.middleware(DbSessionMiddleware())
    dp.callback_query.middleware(DbSessionMiddleware())
    dp.message.middleware(RoleMiddleware())
    dp.callback_query.middleware(RoleMiddleware())

    dp.include_router(user_router)
    dp.include_router(operator_router)
    dp.include_router(admin_router)

    logger.info("Starting HelpDesk bot...")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        await storage.close()


if __name__ == "__main__":
    asyncio.run(main())
